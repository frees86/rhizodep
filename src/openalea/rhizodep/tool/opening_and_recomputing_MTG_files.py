# -*- coding: latin-1 -*-

"""
    This script allows to load MTG (Multiscale Tree Graphs) files from .pckl or .csv files for calculating new variables
     and/or (re)plotting graphs.

    :copyright: see AUTHORS.
    :license: see LICENSE for details.
"""

import os, os.path
from pathlib import Path
import copy

from math import floor

import pickle

import numpy as np
import pandas as pd

from openalea.mtg import *
import openalea.plantgl.all as pgl
from openalea.plantgl.all import *
from PIL import Image, ImageDraw, ImageFont

from openalea.rhizodep.model import recording_MTG_properties
from openalea.rhizodep.tool.tools import (my_colormap, circle_coordinates, plot_mtg,
                                          indexing_root_MTG, creating_a_spatial_scale_MTG)
from openalea.rhizodep.tool.alternative_plotting import plotting_roots_with_pyvista, fast_plotting_roots_with_pyvista


########################################################################################################################
# DEFINING USEFUL FONCTIONS FOR CREATING/IMPROVING IMAGES
########################################################################################################################

# Function creating an image containing a text:
#----------------------------------------------
def drawing_text(text="TEXT !", image_name="text.png", length=220, height=110, font_size=100):
    """
    This function enables to create and save an image showing a text on a transparent background.
    :param text: the text to add
    :param image_name: the name of the image file
    :param length: length of the image
    :param height: height of the image
    :param font_size: the size of the text
    :return:
    """
    # We create a new image:
    im = Image.new("RGB", (length, height), (255, 255, 255, 0))
    # For making it transparent:
    im.putalpha(0)
    # We draw on this image:
    draw = ImageDraw.Draw(im)
    # Relative coordinates of the text:
    (x1, y1) = (0, 0)
    # Defining font type and font size:
    font_time = ImageFont.truetype("./timesbd.ttf", font_size)  # See a list of available fonts on:
    # https:/docs.microsoft.com/en-us/typography/fonts/windows_10_font_list
    # We draw the text on the created image:
    # draw.rectangle((x1 - 10, y1 - 10, x1 + 200, y1 + 50), fill=(255, 255, 255, 200))
    draw.text((x1, y1), text, fill=(0, 0, 0), font=font_time)
    # We save the image as a png file:
    im.save(image_name, 'PNG')
    return

# Function positionning a certain image:
#---------------------------------------
def showing_image(image_name="text.png",
                  x1=0, y1=0, z1=0,
                  x2=0, y2=0, z2=1,
                  x3=0, y3=1, z3=1,
                  x4=0, y4=1, z4=0):
    """
    This function returns the shape corresponding to the image positionned at a certain position.
    :param image_name: the name of the image file
    :param x,y,z for 1-4: x,y,z coordinates of each 4 points of the rectangle containig the image
    :return: the corresponding shape
    """
    # We define the list of points that will correspond to the coordinates of the image to display:
    # points =  [(0,0,0),
    #            (0,0,1),
    #            (0,1,1),
    #            (0,1,0)]
    points = [(x1, y1, z1),
              (x2, y2, z2),
              (x3, y3, z3),
              (x4, y4, z4), ]
    # We define a list of indices:
    indices = [(0, 1, 2, 3)]
    # We define a zone that will correspond to these coordinates:
    carre = pgl.QuadSet(points, indices)
    # We load an image as a texture material:
    my_path = os.path.join("../../simulations/running_scenarios/", image_name)
    tex = pgl.ImageTexture(my_path)
    # We define the texture coordinates that we will use:
    # texCoord = [(0,0),
    #             (0,1),
    #             (1,1),
    #             (1,0)]
    texCoord = [(y1, z1),
                (y2, z2),
                (y3, z3),
                (y4, z4)]
    # And how texture coordinates are associated to vertices:
    texCoordIndices = [(0, 1, 2, 3)]
    # We finally display the new image:
    carre.texCoordList = texCoord
    carre.texCoordIndexList = texCoordIndices
    shape = pgl.Shape(carre, tex)
    # Viewer.display(shape)
    return shape

########################################################################################################################
# DEFINING FUNCTIONS FOR COMPUTING THE DISTRUBUTION OF PROPERTIES ALONG SOIL DEPTH
########################################################################################################################

# Calculation of the length of a root element intercepted between two z coordinates:
# ----------------------------------------------------------------------------------
def sub_length_z(x1, y1, z1, x2, y2, z2, z_first_layer, z_second_layer):
    """
    This function returns the length of a segment postionned between (x1,y1,z1) and (x2,y2,z2) that is located between
    two horizontal planes at z=z_first_layer and z=z_second_layer.
    :return: the computed length between the two planes
    """
    # We make sure that the z coordinates are ordered in the right way:
    min_z = min(z1, z2)
    max_z = max(z1, z2)
    z_start = min(z_first_layer, z_second_layer)
    z_end = max(z_first_layer, z_second_layer)

    # For each row, if at least a part of the root segment formed between point 1 and 2 is included between z_start and z_end:
    if min_z < z_end and max_z >= z_start:
        # The z value to start from is defined as:
        z_low = max(z_start, min_z)
        # The z value to stop at is defined as:
        z_high = min(z_end, max_z)

        # If Z2 is different from Z1:
        if max_z > min_z:
            # Then we calculate the (x,y) coordinates of both low and high points between which length will be computed:
            x_low = (x2 - x1) * (z_low - z1) / (z2 - z1) + x1
            y_low = (y2 - y1) * (z_low - z1) / (z2 - z1) + y1
            x_high = (x2 - x1) * (z_high - z1) / (z2 - z1) + x1
            y_high = (y2 - y1) * (z_high - z1) / (z2 - z1) + y1
            # Geometrical explanation:
            # *************************
            # # The root segment between Start-point (X1, Y1, Z1) and End-Point (X2, Y2, Z2)
            # draws a line in the 3D space which is characterized by the following parametric equation:
            # { x = (X2-X1)*t + X1, y = (Y2-Y1)*t + Y1, z = (Z2-Z1)*t + Z1}
            # To find the coordinates x and y of a new point of coordinate z on this line, we have to solve this system of equations,
            # knowing that: z = (Z2-Z1)*t + Z1, which gives t = (z - Z1)/(Z2-Z1), and therefore:
            # x = (X2-X1)*(z - Z1)/(Z2-Z1) + X1
            # y = (Y2-Y1)*(z - Z1)/(Z2-Z1) + Y1
        # Otherwise, the calculation is much easier, since the whole segment is included in the plan x-y:
        else:
            x_low = x1
            y_low = y1
            x_high = x2
            y_high = y2

        # In every case, the length between the low and high points is computed as:
        inter_length = ((x_high - x_low) ** 2 + (y_high - y_low) ** 2 + (z_high - z_low) ** 2) ** 0.5
    # Otherwise, the root element is not included between z_first_layer and z_second_layer, and intercepted length is 0:
    else:
        inter_length = 0

    # We return the computed length:
    return inter_length

# Integration of root variables within different z_intervals:
# -----------------------------------------------------------
def classifying_on_z(g, z_min=0, z_max=1, z_interval=0.1):
    """
    This function calculates the distribution of certain characteristics of a MTG g according to the depth z.
    For each z-layer between z_min and z_max and each root segment, specific variables are computed, depending on the
    length within the segment that is intercepted between the upper and lower horizontal plane [see 'sub_length' function].
    :param g: the MTG on which calculations are made
    :param z_min: the depth to which we start computing
    :param z_max: the maximal depth to which we stop computing
    :param z_interval: the thickness of each layer to consider between z_min and z_max
    :return: a dictionnary containing the results
    """
    # We initialize empty dictionnaries:
    included_length = {}
    dictionnary_length = {}
    dictionnary_struct_mass = {}
    dictionnary_root_necromass = {}
    dictionnary_surface = {}
    dictionnary_net_hexose_exudation = {}
    dictionnary_hexose_degradation = {}
    final_dictionnary = {}

    # For each interval of z values to be considered:
    for z_start in np.arange(z_min, z_max, z_interval):

        # We create the names of the new properties of the MTG to be computed, based on the current z interval:
        name_length_z = "length_" + str(z_start) + "-" + str(z_start + z_interval) + "_m"
        name_struct_mass_z = "struct_mass_" + str(z_start) + "-" + str(z_start + z_interval) + "_m"
        name_root_necromass_z = "root_necromass_" + str(z_start) + "-" + str(z_start + z_interval) + "_m"
        name_surface_z = "surface_" + str(z_start) + "-" + str(z_start + z_interval) + "_m"
        name_net_hexose_exudation_z = "net_hexose_exudation_" + str(z_start) + "-" + str(z_start + z_interval) + "_m"
        name_hexose_degradation_z = "hexose_degradation_" + str(z_start) + "-" + str(z_start + z_interval) + "_m"
        name_net_rhizodeposition_z = "net_rhizodeposition_" + str(z_start) + "-" + str(z_start + z_interval) + "_m"

        # We (re)initialize total values:
        total_included_length = 0
        total_included_struct_mass = 0
        total_included_root_necromass = 0
        total_included_surface = 0
        total_included_net_hexose_exudation = 0
        total_included_hexose_degradation = 0

        # We cover all the vertices in the MTG:
        for vid in g.vertices_iter(scale=1):
            # n represents the vertex:
            n = g.node(vid)

            # We make sure that the vertex has a positive length:
            if n.length > 0.:
                # We calculate the fraction of the length of this vertex that is included in the current range of z value:
                fraction_length = sub_length_z(x1=n.x1, y1=n.y1, z1=-n.z1, x2=n.x2, y2=n.y2, z2=-n.z2,
                                               z_first_layer=z_start,
                                               z_second_layer=z_start + z_interval) / n.length
                included_length[vid] = fraction_length * n.length
            else:
                # Otherwise, the fraction length and the length included in the range are set to 0:
                fraction_length = 0.
                included_length[vid] = 0.

            # We summed different variables based on the fraction of the length included in the z interval:
            total_included_length += n.length * fraction_length
            total_included_struct_mass += n.struct_mass * fraction_length
            if n.type == "Dead" or n.type == "Just_dead":
                total_included_root_necromass += n.struct_mass * fraction_length
            total_included_surface += n.external_surface * fraction_length
            total_included_net_hexose_exudation += (n.hexose_exudation - n.hexose_uptake_from_soil) * fraction_length
            total_included_hexose_degradation += n.hexose_degradation * fraction_length

        # We record the summed values for this interval of z in several dictionnaries:
        dictionnary_length[name_length_z] = total_included_length
        dictionnary_struct_mass[name_struct_mass_z] = total_included_struct_mass
        dictionnary_root_necromass[name_root_necromass_z] = total_included_root_necromass
        dictionnary_surface[name_surface_z] = total_included_surface
        dictionnary_net_hexose_exudation[name_net_hexose_exudation_z] = total_included_net_hexose_exudation
        dictionnary_hexose_degradation[name_hexose_degradation_z] = total_included_hexose_degradation

        # We also create a new property of the MTG that corresponds to the fraction of length of each node in the z interval:
        g.properties()[name_length_z] = included_length

    # Finally, we merge all dictionnaries into a single one that will be returned by the function:
    final_dictionnary = dict(list(dictionnary_length.items())
                             + list(dictionnary_struct_mass.items())
                             + list(dictionnary_root_necromass.items())
                             + list(dictionnary_surface.items())
                             + list(dictionnary_net_hexose_exudation.items())
                             + list(dictionnary_hexose_degradation.items())
                             )

    return final_dictionnary


# Function for summing or averaging properties for specific groups of root elements, e.g. depending on root order
# or distance from tip:
def computing_data_on_different_roots(g, properties_to_compare=["total_net_rhizodeposition"],
                                      comparing_distance_from_tip=False, distance_treshold=0.04,
                                      summing=True, averaging=False):
    """
    This function enables to compare different groups of roots, which are distinguished by their root order and possibly
    through the distance from root tip. For each root class, the function computes the sum and possibly the mean and the standard deviation
    of the values corresponding to a set of properties of the root MTG.
    :param g: the root MTG to work on
    :param properties_to_compare: a list containing the names of the properties to be considered by the function
    :param comparing_distance_from_tip: if True, roots will be discriminated according to the distance of a root element from the tip of its axis, for each root order
    :param distance_treshold: the critical distance from root tip to consider when segregating roots according to this distance
    :param summing: if True, the function returns the sum of each property within each root class
    :param averaging: if True, the function returns the mean value of each property for a root element within each root class, and its standard deviation
    :return: a dictionnary containing the names of the property x root class x calculation as keys, and the corresponding values
    """

    # -------------------------------------------------------------------------------------------------------------------
    # We quickly define a function that will return the mean value from the items in a list, or 0 if the list is empty,
    # as the traditional functions 'mean' and 'np.mean' throw an error if the list is empty:
    def averaging(list):
        mean_value = sum(list) / len(list) if list else 0.
        return mean_value

    # We do the same for computing standard deviation, even for an empty list:
    def sd(list):
        standard_deviation = np.std(list) if list else 0.
        return standard_deviation

    # -------------------------------------------------------------------------------------------------------------------

    # For preparing the final dictionnary containing the results, we initialize a list of keys and a list of values:
    keys = []
    values = []

    # 1) CREATING LISTS OF SPECIFIC ELEMENTS:
    #########################################

    # We define a list of root elements with positive length for each root order class:
    list_of_elements_all = [vid for vid in g.vertices_iter(scale=1)
                            if g.node(vid).length > 0]
    list_of_elements_order_1 = [vid for vid in g.vertices_iter(scale=1)
                                if g.node(vid).root_order == 1 and g.node(vid).length > 0]
    list_of_elements_order_2 = [vid for vid in g.vertices_iter(scale=1)
                                if g.node(vid).root_order == 2 and g.node(vid).length > 0]
    list_of_elements_higher_orders = [vid for vid in g.vertices_iter(scale=1)
                                      if g.node(vid).root_order > 2 and g.node(vid).length > 0]
    # In addition, if a distinction according to the distance from root tip is to be made:
    if comparing_distance_from_tip:
        # For each root order class, we distinguish a list of root elements close to the root tip from the other elements:
        list_of_elements_all_apical = [vid for vid in list_of_elements_all
                                       if g.node(vid).distance_from_tip <= distance_treshold]
        list_of_elements_all_basal = [vid for vid in list_of_elements_all
                                      if g.node(vid).distance_from_tip > distance_treshold]
        list_of_elements_order_1_apical = [vid for vid in list_of_elements_order_1
                                           if g.node(vid).distance_from_tip <= distance_treshold]
        list_of_elements_order_1_basal = [vid for vid in list_of_elements_order_1
                                          if g.node(vid).distance_from_tip > distance_treshold]
        list_of_elements_order_2_apical = [vid for vid in list_of_elements_order_2
                                           if g.node(vid).distance_from_tip <= distance_treshold]
        list_of_elements_order_2_basal = [vid for vid in list_of_elements_order_2
                                          if g.node(vid).distance_from_tip > distance_treshold]
        list_of_elements_higher_orders_apical = [vid for vid in list_of_elements_higher_orders
                                                 if g.node(vid).distance_from_tip <= distance_treshold]
        list_of_elements_higher_orders_basal = [vid for vid in list_of_elements_higher_orders
                                                if g.node(vid).distance_from_tip > distance_treshold]

    # 2) COMPUTING PROPERTIES ON EACH LIST:
    #######################################

    # First of all, we record the number of elements in each list:
    n_all = len(list_of_elements_all)
    n_1 = len(list_of_elements_order_1)
    n_2 = len(list_of_elements_order_2)
    n_higher = len(list_of_elements_higher_orders)
    # We add the corresponding keys and values for the final results dictionnary:
    keys.extend(["n_all", "n_root_order_1", "n_root_order_2", "n_higher_orders"])
    values.extend([n_all, n_1, n_2, n_higher])
    # In addition, if a distinction according to the distance from root tip is to be made:
    if comparing_distance_from_tip:
        n_all_apical = len(list_of_elements_all_apical)
        n_all_basal = len(list_of_elements_all_basal)
        n_1_apical = len(list_of_elements_order_1_apical)
        n_1_basal = len(list_of_elements_order_1_basal)
        n_2_apical = len(list_of_elements_order_2_apical)
        n_2_basal = len(list_of_elements_order_2_basal)
        n_higher_apical = len(list_of_elements_higher_orders_apical)
        n_higher_basal = len(list_of_elements_higher_orders_basal)
        # We add the corresponding keys and values for the final results dictionnary:
        keys.extend(["n_all_apical", "n_all_basal",
                     "n_root_order_1_apical", "n_root_order_1_basal",
                     "n_root_order_2_apical", "n_root_order_2_basal",
                     "n_higher_orders_apical", "n_higher_orders_basal"])
        values.extend([n_all_apical, n_all_basal, n_1_apical, n_1_basal,
                       n_2_apical, n_2_basal, n_higher_apical, n_higher_basal])

    # Then, for each property to consider:
    for property in properties_to_compare:

        # If the property is to be summed within each list:
        if summing:
            # We sum the property's values of each element within each list of root orders:
            sum_all = sum([g.properties()[property][vid] for vid in list_of_elements_all])
            sum_1 = sum([g.properties()[property][vid] for vid in list_of_elements_order_1])
            sum_2 = sum([g.properties()[property][vid] for vid in list_of_elements_order_2])
            sum_higher = sum([g.properties()[property][vid] for vid in list_of_elements_higher_orders])
            # We add the corresponding keys and values for the final results dictionnary:
            keys.extend([property + "_all_sum",
                         property + "_root_order_1_sum",
                         property + "_root_order_2_sum",
                         property + "_higher_orders_sum"])
            values.extend([sum_all, sum_1, sum_2, sum_higher])
            # In addition, if a distinction according to the distance from root tip is to be made:
            if comparing_distance_from_tip:
                # We sum the property's values of each element within each list segragated with distance from tip:
                sum_all_apical = sum([g.properties()[property][vid] for vid in list_of_elements_all_apical])
                sum_all_basal = sum([g.properties()[property][vid] for vid in list_of_elements_all_basal])
                sum_1_apical = sum([g.properties()[property][vid] for vid in list_of_elements_order_1_apical])
                sum_1_basal = sum([g.properties()[property][vid] for vid in list_of_elements_order_1_basal])
                sum_2_apical = sum([g.properties()[property][vid] for vid in list_of_elements_order_2_apical])
                sum_2_basal = sum([g.properties()[property][vid] for vid in list_of_elements_order_2_basal])
                sum_higher_apical = sum(
                    [g.properties()[property][vid] for vid in list_of_elements_higher_orders_apical])
                sum_higher_basal = sum([g.properties()[property][vid] for vid in list_of_elements_higher_orders_basal])
                # We add the corresponding keys and values for the final results dictionnary:
                keys.extend([property + "_all_apical_sum",
                             property + "_all_basal_sum",
                             property + "_root_order_1_apical_sum",
                             property + "_root_order_1_basal_sum",
                             property + "_root_order_2_apical_sum",
                             property + "_root_order_2_basal_sum",
                             property + "_higher_orders_apical_sum",
                             property + "_higher_orders_basal_sum", ])
                values.extend([sum_all_apical, sum_all_basal,
                               sum_1_apical, sum_1_basal,
                               sum_2_apical, sum_2_basal,
                               sum_higher_apical, sum_higher_basal])

        # If the property is to be averaged within each list:
        if averaging:

            # a) Computing mean values:
            mean_all = averaging([g.properties()[property][vid] for vid in list_of_elements_all])
            mean_1 = averaging([g.properties()[property][vid] for vid in list_of_elements_order_1])
            mean_2 = averaging([g.properties()[property][vid] for vid in list_of_elements_order_2])
            mean_higher = averaging([g.properties()[property][vid] for vid in list_of_elements_higher_orders])
            # We add the corresponding keys and values for the final results dictionnary:
            keys.extend([property + "_all_mean",
                         property + "_root_order_1_mean",
                         property + "_root_order_2_mean",
                         property + "_higher_orders_mean"])
            values.extend([mean_all, mean_1, mean_2, mean_higher])
            # In addition, if a distinction according to the distance from root tip is to be made:
            if comparing_distance_from_tip:
                mean_all_apical = averaging([g.properties()[property][vid] for vid in list_of_elements_all_apical])
                mean_all_basal = averaging([g.properties()[property][vid] for vid in list_of_elements_all_basal])
                mean_1_apical = averaging([g.properties()[property][vid] for vid in list_of_elements_order_1_apical])
                mean_1_basal = averaging([g.properties()[property][vid] for vid in list_of_elements_order_1_basal])
                mean_2_apical = averaging([g.properties()[property][vid] for vid in list_of_elements_order_2_apical])
                mean_2_basal = averaging([g.properties()[property][vid] for vid in list_of_elements_order_2_basal])
                mean_higher_apical = averaging(
                    [g.properties()[property][vid] for vid in list_of_elements_higher_orders_apical])
                mean_higher_basal = averaging(
                    [g.properties()[property][vid] for vid in list_of_elements_higher_orders_basal])
                # We add the corresponding keys and values for the final results dictionnary:
                keys.extend([property + "_all_apical_mean",
                             property + "_all_basal_mean",
                             property + "_root_order_1_apical_mean",
                             property + "_root_order_1_basal_mean",
                             property + "_root_order_2_apical_mean",
                             property + "_root_order_2_basal_mean",
                             property + "_higher_orders_apical_mean",
                             property + "_higher_orders_basal_mean", ])
                values.extend([mean_all_apical, mean_all_basal,
                               mean_1_apical, mean_1_basal,
                               mean_2_apical, mean_2_basal,
                               mean_higher_apical, mean_higher_basal])

            # b) Computing standard deviations:
            sd_all = sd([g.properties()[property][vid] for vid in list_of_elements_all])
            sd_1 = sd([g.properties()[property][vid] for vid in list_of_elements_order_1])
            sd_2 = sd([g.properties()[property][vid] for vid in list_of_elements_order_2])
            sd_higher = sd([g.properties()[property][vid] for vid in list_of_elements_higher_orders])
            # We add the corresponding keys and values for the final results dictionnary:
            keys.extend([property + "_all_sd",
                         property + "_root_order_1_sd",
                         property + "_root_order_2_sd",
                         property + "_higher_orders_sd"])
            values.extend([sd_all, sd_1, sd_2, sd_higher])
            # In addition, if a distinction according to the distance from root tip is to be made:
            if comparing_distance_from_tip:
                sd_all_apical = sd([g.properties()[property][vid] for vid in list_of_elements_all_apical])
                sd_all_basal = sd([g.properties()[property][vid] for vid in list_of_elements_all_basal])
                sd_1_apical = sd([g.properties()[property][vid] for vid in list_of_elements_order_1_apical])
                sd_1_basal = sd([g.properties()[property][vid] for vid in list_of_elements_order_1_basal])
                sd_2_apical = sd([g.properties()[property][vid] for vid in list_of_elements_order_2_apical])
                sd_2_basal = sd([g.properties()[property][vid] for vid in list_of_elements_order_2_basal])
                sd_higher_apical = sd([g.properties()[property][vid] for vid in list_of_elements_higher_orders_apical])
                sd_higher_basal = sd([g.properties()[property][vid] for vid in list_of_elements_higher_orders_basal])
                # We add the corresponding keys and values for the final results dictionnary:
                keys.extend([property + "_all_apical_sd",
                             property + "_all_basal_sd",
                             property + "_root_order_1_apical_sd",
                             property + "_root_order_1_basal_sd",
                             property + "_root_order_2_apical_sd",
                             property + "_root_order_2_basal_sd",
                             property + "_higher_orders_apical_sd",
                             property + "_higher_orders_basal_sd", ])
                values.extend([sd_all_apical, sd_all_basal,
                               sd_1_apical, sd_1_basal,
                               sd_2_apical, sd_2_basal,
                               sd_higher_apical, sd_higher_basal])

    # 3) RECORDING THE RESULTS:
    # We record the results of the computation in a dictionnary:
    dictionary = dict(zip(keys, values))
    dictionnary = {keys[i]: values[i] for i in range(len(keys))}

    return dictionnary

########################################################################################################################
# CREATING A MTG FROM RECORDED FILES AND PERFORMING CALCULATIONS ON IT
########################################################################################################################

# Function for loading a MTG from its properties written in a .csv file:
def create_MTG_from_csv_file(csv_filename='MTG_00003.csv'):

    """
    This function reads a .csv file containing all properties of a MTG to recreate the MTG structure within OpenAlea.
    :param csv_filename: the name of the .csv file to read
    :return: the recreated MTG structure
    """

    # We first read the csv file where all the properties of each vertex has been previously recorded:
    try:
        dataframe = pd.read_csv(csv_filename, sep=',', header=0)
    except:
        print("ERROR: the file", csv_filename,"could not be opened!")

    # We initialize an empty MTG:
    g = MTG()
    # We initialize the first element of the MTG:
    n = g.node(g.add_component(g.root))

    # We define the list of vertices'index to be added to the MTG:
    list_of_vid = dataframe['node_index']
    # We define the list containing the name of each property to add:
    list_of_properties = list(dataframe.columns.values)

    # We assign each property read in the file to an actual property of the MTG:
    for property in list_of_properties:
        # In the special case of "node_index", the old index might not correspond to the new ones in the MTG.
        if property == "node_index":
            # In that case, we rename this property as "original_node_index" to avoid any confusion in the new MTG:
            g.add_property("original_node_index")
        else:
            g.add_property(property)

    # We cover each new vertex to be added to the MTG:
    for index in range(0,len(list_of_vid)):
        # For the current element, we cover all the properties defined in the csv file:
        for property in list_of_properties:
            # For the specific property, we get the single value corresponding to the current vertex ID:
            property_value = dataframe[property].loc[dataframe['node_index'] == list_of_vid[index]].iloc[0]
            # NB: we need to add 'iloc[0]' as the previous expression otherwise returns a series, not a single value.
            # And we finally assign the good value to the good property to the current element.
            if property == "node_index":
                g.properties()["original_node_index"][index+1] = property_value
            else:
                g.properties()[property][index+1] = property_value
        # And if this did not correspond to the last element to be added, we add a new element:
        if index != len(list_of_vid) - 1:
            print("After element", n.index(), "we add a new child!")
            # We now define the next element as the child of the previous element:
            n = n.add_child()

    return g

# MAIN FUNCTION FOR LOADING AND DISPLAYING/EXTRACTING PROPERTIES FROM MTG FILES:
################################################################################
def loading_MTG_files(my_path='',
                      opening_list=False,
                      file_extension='pckl',
                      MTG_directory='MTG_files',
                      single_MTG_filename='root00001.pckl',
                      list_of_MTG_ID=None,
                      plotting_with_PlantGL=False,
                      normal_plotting_with_pyvista=False, show_Pyvista_axes=False,
                      fast_plotting_with_pyvista=False,
                      closing_window=False,
                      factor_of_higher_resolution=3,
                      property="C_hexose_root", vmin=1e-5, vmax=1e-2, log_scale=True, cmap='jet',
                      width=1200, height=1200,
                      x_center=0, y_center=0, z_center=0,
                      x_cam=0, y_cam=0, z_cam=0,
                      step_back_coefficient=0., camera_rotation=False, n_rotation_points=12 * 10,
                      background_color=[0,0,0],
                      root_hairs_display=True,
                      mycorrhizal_fungus_display=False,
                      adding_images_on_plot=False,
                      recording_images=False,
                      images_directory='root_new_images',
                      z_classification=False, z_min=0.0, z_max=1., z_interval=0.1, time_step_in_days=1 / 24.,
                      computing_on_different_roots=False, comparing_distance_from_tip = False, distance_treshold = 0.04,
                      properties_to_compute=["total_net_rhizodeposition", "length"],
                      summing_different_roots=False, averaging_different_roots=False,
                      printing_sum=True,
                      recording_sum=True,
                      printing_warnings=True,
                      recording_g_properties=True,
                      MTG_properties_folder='MTG_properties'):

    """
    This function opens one MTG file or a list of MTG files, displays them and record some of their properties if needed.
    :param my_path: the general file path, in which the directory 'MTG_directory' will be located
    :param opening_list: if True, the function opens all (or some) MTG files located in the 'MTG_directory'
    :param MTG_directory: the name of the directory when MTG files are located
    :param single_MTG_filename: the name of the single MTG to open (if opening_list=False)
    :param list_of_MTG_ID: a list containing the ID number of each MTG to be opened (each MTG name is assumed to be in the format 'rootXXXXX.pckl')
    :param property: the property of the MTG to be displayed
    :param vmin, vmax, log_scale, cmap, width, height, x_center, y_center, z_center, z_cam, camera_distance,
           step_back_coefficient, camera_rotation, n_rotation_points: [cf parameters of the function plot_MTG]
    :param adding_images_on_plot: for adding some additional features on the plots' images
    :param recording_images: if True, images opened in PlantGL will be recorded
    :param images_directory: the name of the directory where images will be recorded
    :param z_classification: if True, specific properties will be integrated or averaged for different z-layers
    :param z_min: the depth to which we start computing
    :param z_max: the maximal depth to which we stop computing
    :param z_interval: the thickness of each layer to consider between z_min and z_max
    :param time_step_in_days: the time step at which is MTG file was generated (used to display time on the images)
    :param computing_on_different_roots: if True, calculations will be done on different root classes
    :param comparing_distance_from_tip: if True, root classes will be based not only on root orders, but also according to the distance from root tip
    :param distance_treshold: the critical distance from root tip to consider when segregating roots according to this distance
    :param properties_to_compute: a list containing the names of the properties to be considered by the function
    :param summing_different_roots: if True, the function returns the sum of each property within each root class
    :param averaging_different_roots: if True, the function returns the mean value of each property for a root element within each root class, and its standard deviation
    :param printing_sum: if True, properties summed over the whole MTG(s) will be shown in the console
    :param recording_sum: if True, properties summed over the whole MTG(s) will be recorded
    :param printing_warnings: if True, warnings will be displayed
    :param recording_g_properties: if True, all the properties of each MTG's node will be recorded in a file
    :param MTG_properties_folder: the specific file path in which MTG properties will be recorded, if any
    :return: The MTG file "g" that was loaded at last.
    """

    # Preparing the folders:
    # -----------------------

    if opening_list:
        # We define the directory "MTG_files":
        g_dir = os.path.join(my_path, MTG_directory)
        print("Loading MTG files located in", g_dir, "...")
    else:
        g_dir = my_path
        print("Loading the MTG file located in", g_dir,"...")

    if recording_images:
        # We define the directory "video"
        video_dir = os.path.join(my_path, images_directory)
        # If this directory doesn't exist:
        if not os.path.exists(video_dir):
            # Then we create it:
            os.mkdir(video_dir)
        else:
            # Otherwise, we delete all the images that are already present inside:
            for root, dirs, files in os.walk(video_dir):
                for file in files:
                    os.remove(os.path.join(root, file))

    if recording_g_properties:
        # We define the directory "MTG_properties_dir"
        properties_dir = os.path.join(my_path,MTG_properties_folder)
        # If this directory doesn't exist:
        if not os.path.exists(properties_dir):
            # Then we create it:
            os.mkdir(properties_dir)
        else:
            # Otherwise, we delete all the files that are already present inside:
            for root, dirs, files in os.walk(properties_dir):
                for file in files:
                    os.remove(os.path.join(root, file))

    # Depending on the extension of the file, we may either consider pickle files or csv files containing
    # all the properties of the MTG:
    if file_extension == 'pckl':
        # We get the list of the names of all MTG files:
        filenames = Path(g_dir).glob('*pckl')
    elif file_extension == 'csv':
        # We get the list of the names of all MTG files:
        filenames = Path(g_dir).glob('*csv')
    else:
        print("!!! ERROR: the file extension can only be 'pckl' or 'csv'!!!")
        return

    filenames = sorted(filenames)
    # We initialize a list containing the numbers of the MTG to be opened:
    list_of_MTG_numbers = []

    # If the instructions are to open the whole list of MTGs in the directory and not a subset of it:
    if opening_list and not list_of_MTG_ID:
        # We cover each name of MTG ending as 'rootXXXX.pckl' (where X is a digit), extract the corresponding number,
        # and add it to the list:
        for filename in filenames:
            if file_extension == 'pckl':
                MTG_ID = int(str(filename)[-10:-5])
            else:
                MTG_ID = int(str(filename)[-9:-4])
            list_of_MTG_numbers.append(MTG_ID)
    # If the instructions are to open a specific list:
    elif opening_list and list_of_MTG_ID:
        list_of_MTG_numbers =  list_of_MTG_ID
    # Otherwise, we open a single file:
    else:
        list_of_MTG_numbers = [int(str(single_MTG_filename)[-10:-5])]

    # In addition, we get the final list of properties corresponding to the last MTG of the list.
    # We first load the last MTG of the list:
    ID = list_of_MTG_numbers[-1]
    if file_extension == 'pckl':
        filename = 'root%.5d.pckl' % ID
        MTG_path = os.path.join(g_dir, filename)
        f = open(MTG_path, 'rb')
        g = pickle.load(f)
        f.close()
    else:
        filename = 'root%.5d.csv' % ID
        MTG_path = os.path.join(g_dir, filename)
        g = create_MTG_from_csv_file(csv_filename=MTG_path)
    # And we define the final list of properties to record according to all the properties of this MTG:
    list_of_properties = list(g.properties().keys())
    # We sort it alphabetically:
    list_of_properties.sort(key=str.lower)

    if z_classification:
        # We create an empty dataframe that will contain the results of z classification:
        z_dictionnary_series = []

    if computing_on_different_roots:
        # We create an empty dataframe that will contain the results of computing:
        computing_dictionnary_series = []

    # If the camera is supposed to move around the MTG:
    if camera_rotation:
        # We record the initial distance of the camera from the center:
        initial_camera_distance = max(x_cam, y_cam)
        camera_distance = initial_camera_distance
        # We initialize the index for reading each coordinates:
        index_camera = 0
        # We calculate the coordinates of the camera on the circle around the center:
        x_coordinates, y_coordinates, z_coordinates = circle_coordinates(z_center=z_cam,
                                                                         radius=camera_distance,
                                                                         n_points=n_rotation_points)

    # We cover each of the MTG files in the list (or only the specified file when requested):
    # ---------------------------------------------------------------------------------------
    for MTG_position in range(0,len(list_of_MTG_numbers)):

        # Loading the MTG file:
        #----------------------
        ID = list_of_MTG_numbers[MTG_position]
        print("Dealing with MTG", ID, "-", MTG_position+1,"out of", len(list_of_MTG_numbers), "MTGs to consider...")

        if file_extension == 'pckl':
            filename = 'root%.5d.pckl' % ID
            MTG_path = os.path.join(g_dir, filename)
            f = open(MTG_path, 'rb')
            g = pickle.load(f)
            f.close()
        else:
            filename = 'root%.5d.csv' % ID
            MTG_path = os.path.join(g_dir, filename)
            g = create_MTG_from_csv_file(csv_filename=MTG_path)
        print("   > New MTG opened!")

        # Plotting the MTG:
        # ------------------
        if recording_images:
            # We define the name of the image:
            image_name = os.path.join(video_dir, 'root%.5d.png' % ID)
        else:
            image_name = "plot.png"

        # If the rotation of the camera around the root system is required:
        if camera_rotation:
            # We redefine the position of the camera according to the pre-registered circle coordinates around the MTG:
            x_cam = x_coordinates[index_camera]
            y_cam = y_coordinates[index_camera]
            z_cam = z_coordinates[index_camera]
            # And we move the index for the next plot:
            index_camera += 1
            # If this index is higher than the number of coordinates in each vector:
            if index_camera >= n_rotation_points:
                # Then we reset the index to 0:
                index_camera = 0
            # If the camera is also supposed to change its distance from the center:
            if step_back_coefficient != 0.:
                # Then we increase the distance according to the step_back_coefficient:
                camera_distance += initial_camera_distance * step_back_coefficient
                # And we re-calculate the coordinates of the camera on the circle around the center, used at the next image:
                x_coordinates, y_coordinates, z_coordinates = circle_coordinates(z_center=z_cam,
                                                                                 radius=camera_distance,
                                                                                 n_points=n_rotation_points)

        # CASE 1: the MTG is to be plot with Pyvista
        #-------------------------------------------
        if normal_plotting_with_pyvista or fast_plotting_with_pyvista:

            # We color the MTG according to the property:
            my_colormap(g, property_name=property, cmap='jet', vmin=vmin, vmax=vmax, lognorm=log_scale)
            print("   > Trying to plot...")
            if normal_plotting_with_pyvista:
                # We plot the current file:
                plotting_roots_with_pyvista(g, displaying_root_hairs=root_hairs_display,
                                            showing=False, recording_image=recording_images, image_file=image_name,
                                            factor_of_higher_resolution=factor_of_higher_resolution,
                                            background_color=background_color,
                                            plot_width=width, plot_height=height,
                                            camera_x=x_cam, camera_y=y_cam, camera_z=z_cam,
                                            focal_x=x_center, focal_y=y_center, focal_z=z_center,
                                            closing_window=closing_window,
                                            show_axes=show_Pyvista_axes)
            else:
                # We plot the current file:
                fast_plotting_roots_with_pyvista(g, displaying_root_hairs=root_hairs_display,
                                                 showing=False, recording_image=recording_images, image_file=image_name,
                                                 factor_of_higher_resolution=factor_of_higher_resolution,
                                                 background_color=background_color,
                                                 plot_width=width, plot_height=height,
                                                 camera_x=x_cam, camera_y=y_cam, camera_z=z_cam,
                                                 focal_x=x_center, focal_y=y_center, focal_z=z_center,
                                                 closing_window=closing_window)

            # If the camera is supposed to move away at the next image, then we move the camera further from the root system:
            x_cam = x_cam * (1 + step_back_coefficient)
            z_cam = z_cam * (1 + step_back_coefficient)

            print("   > Plot made!")
            print("")

        # CASE 2: the MTG is to be plot with PlantGL
        #-------------------------------------------
        elif plotting_with_PlantGL:
            # We create the general scene:
            sc = plot_mtg(g, prop_cmap=property, lognorm=log_scale, vmin=vmin, vmax=vmax, cmap=cmap,
                                 width=width,
                                 height=height,
                                 x_center=x_center,
                                 y_center=y_center,
                                 z_center=z_center,
                                 x_cam=x_cam,
                                 y_cam=y_cam,
                                 z_cam=z_cam,
                                 background_color=background_color,
                                 root_hairs_display=root_hairs_display,
                                 mycorrhizal_fungus_display=mycorrhizal_fungus_display)

            # In case we want to add text:
            if adding_images_on_plot:
                text = "t = 100 days"
                # length_text=len(text)*50
                # height_text = 120
                length_text = 600
                height_text = 600
                font_size = 100
                drawing_text(text=text, length=length_text, height=height_text, font_size=font_size, image_name="text.png")
                # Adding text to the plot:
                lower_left_x = 3
                lower_left_y = -2
                lower_left_z = -2
                length = 1
                height = 1
                shape1 = showing_image(image_name="text.png",
                                       x1=lower_left_x, y1=lower_left_y, z1=lower_left_z,
                                       x2=lower_left_x, y2=lower_left_y, z2=lower_left_z + height,
                                       x3=lower_left_x, y3=lower_left_y + length, z3=lower_left_z + height,
                                       x4=lower_left_x, y4=lower_left_y + length, z4=lower_left_z
                                       )
                # Viewer.display(shape)
                sc += shape1

                # Adding colorbar to the plot:
                # Adding text to the plot:
                lower_left_x = 6.5
                lower_left_y = -1
                lower_left_z = -3.8
                length = 1
                height = 1
                shape2 = showing_image(image_name="colorbar_new.png",
                                       x1=lower_left_x, y1=lower_left_y, z1=lower_left_z,
                                       x2=lower_left_x, y2=lower_left_y, z2=lower_left_z + height,
                                       x3=lower_left_x, y3=lower_left_y + length, z3=lower_left_z + height,
                                       x4=lower_left_x, y4=lower_left_y + length, z4=lower_left_z
                                       )
                # Viewer.display(shape)
                sc += shape2

            # We finally display the MTG on PlantGL:
            pgl.Viewer.display(sc)
            # And we record its image:
            if recording_images:
                image_name = os.path.join(video_dir, 'root%.5d.png')
                pgl.Viewer.saveSnapshot(image_name % ID)

            # If the camera is supposed to move away at the next image, then we move the camera further from the root system:
            x_cam = x_cam * (1 + step_back_coefficient)
            z_cam = z_cam * (1 + step_back_coefficient)

            print("   > Plot made!")
            print("")

        # For recording the properties of g in a csv file:
        # ------------------------------------------------
        if recording_g_properties:
            # We define the final list of properties to record according to all the properties of this MTG:
            list_of_properties = list(g.properties().keys())
            # We sort it alphabetically:
            list_of_properties.sort(key=str.lower)
            prop_file_name = os.path.join(properties_dir, 'root%.5d.csv')
            recording_MTG_properties(g, file_name=prop_file_name % ID, list_of_properties=list_of_properties)

        # For integrating root variables on the z axis:
        # ----------------------------------------------
        if z_classification:
            # We perform the classification for the current MTG, which generates a dictionnary:
            z_dictionnary = classifying_on_z(g, z_min=z_min, z_max=z_max, z_interval=z_interval)
            # We add a new item in the dictionnary containing the time to which this MTG corresponds:
            z_dictionnary["time_in_days"] = time_step_in_days * ID
            # We add the dictionnary to the dataframe containing the results of z-classfication for all MTG files:
            z_dictionnary_series.append(z_dictionnary)

        # For computing variables among different types of roots:
        # -------------------------------------------------------
        if computing_on_different_roots:
            # We perform the computing for the current MTG, which generates a dictionnary:
            dictionnary = computing_data_on_different_roots(g, properties_to_compare=properties_to_compute,
                                                            comparing_distance_from_tip=comparing_distance_from_tip,
                                                            distance_treshold=distance_treshold,
                                                            summing=summing_different_roots,
                                                            averaging=averaging_different_roots)
            # We add a new item in the dictionnary containing the time to which this MTG corresponds:
            dictionnary["time_in_days"] = time_step_in_days * ID
            # We add the dictionnary to the dataframe containing the results of computing for all MTG files:
            computing_dictionnary_series.append(dictionnary)

    #-------------------------------------------------------------------------------------------------------------------

    # At the end of the loop, we can record the classification according to z:
    if z_classification:
        # We create a data_frame from the vectors generated in the main program up to this point:
        data_frame_z = pd.DataFrame.from_dict(z_dictionnary_series)
        # For clarity, we move the last column "time_in_days" to the first column:
        col = data_frame_z.pop('time_in_days')
        data_frame_z.insert(0, col.name, col)
        # We save the data_frame in a CSV file:
        z_file_path = os.path.join(my_path, 'z_classification.csv')
        data_frame_z.to_csv(z_file_path, na_rep='NA', index=False, header=True)
        print("   > A new file 'z_classification.csv' has been saved.")

    # And we can record the computing among different root classes:
    if computing_on_different_roots:
        # We create a data_frame from the vectors generated in the main program up to this point:
        data_frame_computing = pd.DataFrame.from_dict(computing_dictionnary_series)
        # For clarity, we move the last column "time_in_days" to the first column:
        col = data_frame_computing.pop('time_in_days')
        data_frame_computing.insert(0, col.name, col)
        # We save the data_frame in a CSV file:
        computing_file_path = os.path.join(my_path, 'computing_different_root_classes.csv')
        data_frame_computing.to_csv(computing_file_path, na_rep='NA', index=False, header=True)
        print("   > A new file 'computing_different_root_classes.csv' has been saved.")

    return g

########################################################################################################################
# MAIN FUNCTIONS FOR AVERAGING SEVERAL MTG INTO ONE
########################################################################################################################

# Function for creating one average MTG from a list of MTG:
#----------------------------------------------------------
def averaging_a_list_of_MTGs(list_of_MTG_numbers=[143, 167, 191], list_of_properties=[],
                             directory_path = 'MTG_files', recording_averaged_MTG=True,
                             averaged_MTG_name=None,
                             recording_directory = 'averaged_MTG_files'):
    """
    This function calculate an "averaged" MTG that, for the property of a given node, attributes the mean value of that
    property value for the same node found in a list of MTG. This is especially useful for calculating mean values over
    a time range.
    :param list_of_MTG_numbers: a list containing the ID number of each MTG to be opened (each MTG name is assumed to be in the format 'rootXXXXX.pckl')
    :param list_of_properties: a list containing the names of the properties to average
    :param directory_path: the path of the directory where MTG files are stored
    :param recording_averaged_MTG: if True, the calculated averaged MTG will be recorded
    :param averaged_MTG_name: the name of the new averaged MTG file
    :param recording_directory: the directory in which the new averaged MTG will be recorded
    :return: the new averaged MTG
    """

    # If the new MTG file is to be recorded:
    if recording_averaged_MTG:
        # We check the directory where the average MTG will be recorded:
        if not os.path.exists(recording_directory):
            # Then we create it:
            os.mkdir(recording_directory)

    # We initialize the list of MTG:
    list_of_MTGs = []
    # We open all the MTG, as specified from the list of MTG numbers:
    for number in list_of_MTG_numbers:
        filename = os.path.join(directory_path, 'root%.5d.pckl' % number).replace("//", "/")
        f = open(filename, 'rb')
        g = pickle.load(f)
        f.close()
        list_of_MTGs.append(g)

    # We initialize the number of vertices in the final MTG:
    n_vertices = 0
    # We cover all the MTG in the list and compare their number of vertices, so that we select the MTG with the highest
    # number of vertices, which will be the frame of the new, average MTG:
    for g in list_of_MTGs:
        if g.nb_vertices() > n_vertices:
            n_vertices = g.nb_vertices()
            averaged_MTG = g

    # We make sure that the list of properties is not empty:
    if list_of_properties == [] or list_of_properties == None:
        print("NOTE: as the list of required properties was empty, we considered all the properties of the MTG.")
        list_of_properties = list(averaged_MTG.properties().keys())

    # We cover each possible vertex in the MTGs:
    for vid in averaged_MTG.vertices_iter(scale=1):
        # We cover each property to be averaged:
        for property in list_of_properties:
            # We initialize an empty list that will contain the values to be averaged:
            temporary_list = []
            # We cover each MTG in the list of MTGs:
            for g in list_of_MTGs:
                # We try to access the value corresponding to the specific property, MTG and vertex:
                try:
                    value = g.property(property)[vid]
                    # If it exists, we add this value to the list:
                    temporary_list.append(value)
                except:
                    # Otherwise, we add a NA value instead:
                    temporary_list.append(np.nan)

            # For the current property, we check whether the list of values of each MTG contains numeric values or not:
            testing_if_numeric = any(isinstance(item, (int, float, complex)) for item in temporary_list)
            # If the list contains numerical values:
            if testing_if_numeric is True:
                # Then we calculate the mean value from the list (or add NA if it cannot be calculated):
                try:
                    mean_value = np.nanmean(temporary_list)
                except:
                    mean_value = np.nan
                # And we assign the mean value to the vertex in the averaged MTG:
                averaged_MTG.property(property)[vid] = mean_value
            else:
                # Otherwise we assign the original value of the last MTG to the vertex in the averaged MTG:
                averaged_MTG.property(property)[vid] = g.property(property)[vid]

    if recording_averaged_MTG:
        # If no specific name for the averaged MTG has been specified:
        if not averaged_MTG_name:
            first = list_of_MTG_numbers[0]
            last = list_of_MTG_numbers[-1]
            print("We record the averaged MTG calculated from the list", first,"-",last," in the directory", os.getcwd())
            new_name = 'averaged_root_' + str(first) + '_' + str(last) + '.pckl'
        else:
            new_name=averaged_MTG_name
        # We record the averaged MTG:
        g_file_name = os.path.join(recording_directory, new_name)
        with open(g_file_name, 'wb') as output:
            pickle.dump(averaged_MTG, output, protocol=2)

    return  averaged_MTG

# # Example:
# averaged_MTG = averaging_a_list_of_MTGs(list_of_MTG_numbers=range(0,23),
#                                         list_of_properties=['length', 'C_hexose_root'],
#                                         directory_path = 'C:/Users/frees/rhizodep/simulations/running_scenarios/outputs/Scenario_0097/MTG_files/',
#                                         recording_directory='C:/Users/frees/rhizodep/simulations/running_scenarios/outputs/Scenario_0097/averaged_MTG_files/')

# Function for creating many averaged MTG when covering a large list of MTG files:
#---------------------------------------------------------------------------------
def averaging_through_a_series_of_MTGs(MTG_directory='MTG_files',
                                       list_of_MTG_numbers_to_average=[],
                                       list_of_properties=[],
                                       odd_number_of_MTGs_for_averaging = 3,
                                       recording_averaged_MTG=True,
                                       recording_directory='averaged_MTG_files'):
    """
    This function covers each MTG in a directory, and for each one calculates an averaged MTG based on a specific number
    of MTG files (located right before and right after the current MTG in the list), for a certain list of properties.
    Ex: for the MTG 'root00005.pckl', the new averaged MTG 'root00004.pckl' will be calculated from 'root00004.pckl',
    'root00005.pckl' and 'root00006.pckl' if the specified number of MTGs to average is 3. This may not be exactly true
    for the very first or very last MTG files (they are averaged on either only the subsequent MTG files or only the
    preceding files, respectively).
    :param MTG_directory: the path of the directory in which MTG files are stored
    :param list_of_properties: a list containing the names of the properties to average
    :param odd_number_of_MTGs_for_averaging: an odd number (i.e. 1, 3, 5, 7, etc) that corresponds to the total number of MTG for averaging
    :param recording_averaged_MTG: if True, the new averaged MTG files will be recorded
    :param recording_directory: the name of the directory in which the new averaged MTG files will be saved
    :return:
    """

    print("We now calculate a mean MTG averaged over", odd_number_of_MTGs_for_averaging,
          "successive MTGs, for each MTG present in the directory", MTG_directory, "...")

    # We organize the output folder:
    if recording_averaged_MTG:
        # If the directory where the average MTG will be recorded does not exist:
        if not os.path.exists(recording_directory):
            # Then we create it:
            os.mkdir(recording_directory)
        else:
            # Otherwise, we delete all the files that are already present inside:
            for root, dirs, files in os.walk(recording_directory):
                for file in files:
                    os.remove(os.path.join(root, file))

    # We calculate the number of MTG at a higher or lower position compared to the targeted MTG to include when averaging:
    half_number = floor(odd_number_of_MTGs_for_averaging/2.)
    # For example, if the odd number is 7, then we will average the MTG together with 3 MTG located before it and 3 MTG
    # located after it.

    # DEFINING A LIST CONTAINING THE ID NUMBER OF ALL MTG FILES IN THE DIRECTORY:
    # We create a list containing the path of each MTG files in the directory:
    filenames = Path(MTG_directory).glob('*pckl')
    # We convert the path of each MTG to a string:
    filenames = [str(path) for path in filenames]
    # We reorder the MTG files if needed, from the lowest to the highest number:
    filenames = sorted(filenames)
    # We create a second list containing only the ID numbers of these MTG files:
    complete_list_of_MTG_ID=[]
    # For each MTG path in the list 'filenames':
    for position in range(0, len(filenames)):
        # We get the full name of the MTG file, ending by 'rootXXXXX.pckl', where X is a digit:
        MTG_path = filenames[position]
        # We extract the characters corresponding to the ID number of the MTG, and convert it to an integer:
        MTG_ID = int(str(MTG_path)[-10:-5])
        # We add the number to the complete list of MTG numbers in the directory:
        complete_list_of_MTG_ID.append(MTG_ID)

    # DEFINING THE LIST OF TARGETED MTG NUMBERS:
    # If the user has not specified a dedicated list of specific MTG to average within the directory of MTG files,
    # we assume that all MTG files in the directory have to be averaged:
    if list_of_MTG_numbers_to_average == [] or list_of_MTG_numbers_to_average == None:
        list_of_MTG_numbers_to_average = complete_list_of_MTG_ID
    # Otherwise, this list has already been defined.

    # COVERING EACH MTG TO BE AVERAGED:
    # We cover each desired MTG file in the directory:
    for target_MTG_ID in list_of_MTG_numbers_to_average:

        # 1) We define the list that will contain the final ID numbers of the MTG files to average for the targeted MTG.
        # We first initialize it.
        MTG_list_to_average=[]
        # We cover each potential MTG number to be averaged for the targeted MTG:
        for ID in range(target_MTG_ID - half_number, target_MTG_ID + half_number):
            # We check that this theoretical ID number actually exists in the MTG number lists:
            if ID in complete_list_of_MTG_ID:
                # If so, we add its ID to the final list of MTG numbers to be averaged for the specific targeted MTG file:
                MTG_list_to_average.append(ID)
            # If not, maybe the targeted position is at the beginning or end of the complete list of MTG in the directory.
            # In such case, we just move to the next possible ID number.

        # 2) Eventually, we proceed to the averaging using the function 'averaging_a_list_of_MTGs':
        print("For the MTG", str(target_MTG_ID), "we average over the MTGs' list", MTG_list_to_average, "...")
        averaged_MTG = averaging_a_list_of_MTGs(list_of_MTG_numbers=MTG_list_to_average,
                                                list_of_properties=list_of_properties,
                                                directory_path=MTG_directory,
                                                recording_averaged_MTG=recording_averaged_MTG,
                                                averaged_MTG_name='root%.5d.pckl' % target_MTG_ID,
                                                recording_directory=recording_directory)

    return

# # Example:
# averaging_through_a_series_of_MTGs(MTG_directory='C:/Users/frees/rhizodep/simulations/running_scenarios/outputs/Scenario_0097/MTG_files',
#                                    list_of_properties=['length', 'C_hexose_root'],
#                                    odd_number_of_MTGs_for_averaging=7,
#                                    recording_averaged_MTG=True,
#                                    recording_directory='C:/Users/frees/rhizodep/simulations/running_scenarios/outputs/Scenario_0097/averaged_MTG_files')

########################################################################################################################
# # ISOLATING A FRACTION OF THE MTG BASED ON TOPOLOGICAL COORDINATES
########################################################################################################################

# Function for removing or making invisible different axes and subaxes from a root MTG:
def subsampling_a_MTG(g, string_of_axis_ID_to_remove="Ax1-S1-", expected_starting_index_of_string = 0,
                      maximal_string_length_of_axis_ID=-1,
                      create_a_new_MTG = False):
    """
    This function aims to provide a root MTG for showing only a few axes from it, based on the property 'axis_ID'
    that corresponds to a chain of characters describing the position of each root element in the topology of the MTG.
    The function will look for a specific chain of characters starting at a specific position within the string "axis_ID',
    and will either remove all corresponding axes, or reduce their length to 0 so that they are not shown.
    :param g: the root MTG to subsample
    :param string_of_axis_ID_to_remove: specific chain of characters to detect within 'axis_ID' for removing axes
    :param expected_starting_index_of_string: starting index of the chain of characters to detect within 'axis_ID'
    :param create_a_new_MTG: if True, a new MTG containing only the remaining axes will be created;
                             if False, the original MTG will be modified by setting the length of all removed axes to 0.
    :return:
    """

    # If we wish to return a new MTG and not modify the original one, we create a copy of the MTG with all its properties:
    if create_a_new_MTG:
        print("Creating a copy of the MTG...")
        new_g = copy.deepcopy(g)

    print("Subsampling the new MTG...")
    # We cover each node of the MTG:
    for vid in g.vertices_iter(scale=1):
        # We get the current node:
        n = g.node(vid)
        # We reinitialize the decision to remove the current element:
        removal = False
        # If the current element has an axis_ID that contains the specific string starting at the specified position:
        # ( Note: the operator "finds" returns the index of the left character of the substring found in the main string,
        # otherwise it returns -1)
        if n.axis_ID.find(string_of_axis_ID_to_remove) == expected_starting_index_of_string:
            removal = True
        if maximal_string_length_of_axis_ID > 0 and len(n.axis_ID) > maximal_string_length_of_axis_ID:
            removal = True
        # Eventually, if one of these conditions is filled:
        if removal:
            # If we have decided to create a new MTG while keeping the original one intact:
            if create_a_new_MTG:
                # We remove the current vertex and all subsequent children vertices from the copy of the MTG:
                new_g.remove_tree(vid)
            # Otherwise, we will modify the original MTG, but won't remove any of its elements:
            else:
                # We don't want to display seminal or adventitious axes, so we set their length to 0
                # but we save their original length in a new property:
                n.original_length = n.length
                n.length = 0

    # We finally return either the new truncated MTG or the original one that has been modified:
    if create_a_new_MTG:
        return new_g
    else:
        return g

# # Example:
#
# # We compute the new property "axis_ID" that gives an identifyer to each element based on the topology of the MTG:
# indexing_root_MTG(g)
# # Here, we want to remove all root elements but the elements from the main seminal axis. We will therefore look for
# # each vertex having an axis_ID beginning by "Ax1-S1-" (i.e. with "Ax1-S1-" starting at the index 0 of the chain of
# # characters), since all other seminal and nodal roots emerge from the first segment of the first axis:
# MTG_to_display = subsampling_a_MTG(g, string_of_axis_ID_to_remove="Ax1-S1-", expected_starting_index_of_string = 0,
#                                    create_a_new_MTG = True)

def showing_one_axis(my_path='',
                     opening_list=False,
                     file_extension='pckl',
                     MTG_directory='MTG_files',
                     single_MTG_filename='root00001.pckl',
                     list_of_MTG_ID=None,
                     starting_string_of_axes_to_remove="Ax00001-Se00001-",
                     targeted_apex_axis_ID="Ax00001-Ap00000",
                     maximal_string_length_of_axis_ID=-1,
                     recording_new_MTG_files=False,
                     new_MTG_files_folder=os.path.join('axis_MTG_files'),
                     recording_new_MTG_properties=True,
                     new_MTG_properties_folder=os.path.join('axis_MTG_properties'),
                     plotting=True,
                     property_name="net_rhizodeposition_rate_per_day_per_cm",
                     vmin=1e-8, vmax=1e-5, lognorm=True, cmap='jet',
                     images_directory="axis_images"):

    """
    This function enables to reduce a MTG to only one axis, e.g. for illustrating how variables vary along it.
    :param my_path: the path of the main directory
    :param opening_list: if True, the function will look at a list of different files to be opened
    :param file_extension: the extension of the file for loading the MTG (either 'pckl' or 'csv')
    :param MTG_directory: the name of the folder where MTG files are stored
    :param single_MTG_filename: if opening_list is False, this corresponds to the name of the MTG file to open
    :param list_of_MTG_ID: if opening_list is True, this corresponds to the list of MTG names to open
    :param starting_string_of_axes_to_remove: the starting characters common to all axes to be removed
    :param targeted_apex_axis_ID: the axis_ID of the apex corresponding to the axis to keep
    :param maximal_string_length_of_axis_ID: the maximal number of characters within axis_ID to be kept, so that elements with a higher numbers (e.g. lateral roots) will be removed
    :param recording_new_MTG_files: if True, the new single-axis MTG files will be recorded as pickle files
    :param new_MTG_files_folder: the name of the folder where new single-axis MTG should be recorded
    :param recording_new_MTG_properties: if True, all properties from each new single-axis MTG files will be recorded in a .csv file
    :param new_MTG_properties_folder: the name of the folder where the properties of new single-axis MTG should be recorded
    :param plotting: if True, the new single-axis MTG files will be displayed
    :param property_name: the name of the property of the new MTG files to be displayed
    :param vmin: the minimal value shown on the colorbar
    :param vmax: the maximal value shown on the colorbar
    :param lognorm: if True, the colorbar will be displayed in log-scale
    :param cmap: the name of the color distribution within the colorbar
    :param images_directory: the name of the folder where the images of new single-axis MTG should be recorded
    """

    # If a list of MTG files is to be opened:
    if opening_list:
        # We define the directory "MTG_files":
        g_dir = os.path.join(my_path, MTG_directory)
    else:
        g_dir = my_path
    print("Loading the MTG file located in", g_dir,"...")
    # If plots are to be printed:
    if plotting:
        # We define the directory "video"
        video_dir = os.path.join(my_path, images_directory)
        # If this directory doesn't exist:
        if not os.path.exists(video_dir):
            # Then we create it:
            os.mkdir(video_dir)
        else:
            # Otherwise, we delete all the images that are already present inside:
            for root, dirs, files in os.walk(video_dir):
                for file in files:
                    os.remove(os.path.join(root, file))

    # Depending on the extension of the file, we may either consider pickle files or csv files containing
    # all the properties of the MTG:
    if file_extension == 'pckl':
        # We get the list of the names of all MTG files:
        filenames = Path(g_dir).glob('*pckl')
    elif file_extension == 'csv':
        # We get the list of the names of all MTG files:
        filenames = Path(g_dir).glob('*csv')
    else:
        print("!!! ERROR: the file extension can only be 'pckl' or 'csv'!!!")
        return

    filenames = sorted(filenames)
    # We initialize a list containing the numbers of the MTG to be opened:
    list_of_MTG_numbers = []

    # If the instructions are to open the whole list of MTGs in the directory and not a subset of it:
    if opening_list and not list_of_MTG_ID:
        # We cover each name of MTG ending as 'rootXXXX.pckl' (where X is a digit), extract the corresponding number,
        # and add it to the list:
        for filename in filenames:
            if file_extension == 'pckl':
                MTG_ID = int(filename[-10:-5])
            else:
                MTG_ID = int(filename[-9:-4])
            list_of_MTG_numbers.append(MTG_ID)
    # If the instructions are to open a specific list:
    elif opening_list and list_of_MTG_ID:
        list_of_MTG_numbers =  list_of_MTG_ID
    # Otherwise, we open a single file:
    else:
        if file_extension == 'pckl':
            list_of_MTG_numbers = [int(single_MTG_filename[-10:-5])]
        else:
            list_of_MTG_numbers = [int(single_MTG_filename[-9:-4])]

    if recording_new_MTG_files:
        # We define the directory "MTG_properties":
        prop_dir = os.path.join(my_path, new_MTG_files_folder)
        # If this directory doesn't exist:
        if not os.path.exists(prop_dir):
            # Then we create it:
            os.mkdir(prop_dir)
        else:
            # Otherwise, we delete all the files that are already present inside:
            for root, dirs, files in os.walk(prop_dir):
                for file in files:
                    os.remove(os.path.join(root, file))

    if recording_new_MTG_properties:
        # We define the directory "MTG_properties":
        prop_dir = os.path.join(my_path, new_MTG_properties_folder)
        # If this directory doesn't exist:
        if not os.path.exists(prop_dir):
            # Then we create it:
            os.mkdir(prop_dir)
        else:
            # Otherwise, we delete all the files that are already present inside:
            for root, dirs, files in os.walk(prop_dir):
                for file in files:
                    os.remove(os.path.join(root, file))
        # In addition, we get the final list of properties corresponding to the last MTG of the list.
        # We first load the last MTG of the list:
        ID = list_of_MTG_numbers[-1]
        if file_extension == 'pckl':
            filename = 'root%.5d.pckl' % ID
            MTG_path = os.path.join(g_dir, filename)
            f = open(MTG_path, 'rb')
            g = pickle.load(f)
            f.close()
        else:
            filename = 'root%.5d.csv' % ID
            MTG_path = os.path.join(g_dir, filename)
            g = create_MTG_from_csv_file(csv_filename=MTG_path)

        # And we define the final list of properties to record according to all the properties of this MTG:
        list_of_properties = list(g.properties().keys())
        list_of_properties.sort(key=str.lower)

    # We cover each of the MTG files in the list (or only the specified file when requested):
    # ---------------------------------------------------------------------------------------
    for MTG_position in range(0, len(list_of_MTG_numbers)):

        # Loading the MTG file:
        # ----------------------
        ID = list_of_MTG_numbers[MTG_position]
        print("Dealing with MTG", ID, "-", MTG_position + 1, "out of", len(list_of_MTG_numbers),
              "MTGs to consider...")

        if file_extension == 'pckl':
            filename = 'root%.5d.pckl' % ID
            MTG_path = os.path.join(g_dir, filename)
            f = open(MTG_path, 'rb')
            g = pickle.load(f)
            f.close()
        else:
            filename = 'root%.5d.csv' % ID
            MTG_path = os.path.join(g_dir, filename)
            g = create_MTG_from_csv_file(csv_filename=MTG_path)
        print("   > New MTG opened!")

        # COMPUTING THE 'AXIS_ID' PROPERTY:
        # We compute the new property "axis_ID" that gives an identifyer to each element based on the topology of the MTG:
        print("Indexing root axes...")
        indexing_root_MTG(g)
        # print("Here are the values of axis_ID for the whole MTG:")
        # print(g.properties()['axis_ID'])

        # SUBSAMPLING THE MTG:
        # Here, we want to remove all root elements but the elements from the main seminal axis. We will therefore look for
        # each vertex having an axis_ID beginning by "Ax1-S1-" (i.e. starting at the index 0 of the chain of characters),
        # since all other seminal and nodal roots emerge from the first segment of the first axis.
        # We also exclude lateral roots from the main axis by specifying a maximal number of characters allowed in axis_ID:
        MTG_to_display = subsampling_a_MTG(g,
                                           string_of_axis_ID_to_remove=starting_string_of_axes_to_remove,
                                           expected_starting_index_of_string=0,
                                           maximal_string_length_of_axis_ID=maximal_string_length_of_axis_ID,
                                           create_a_new_MTG=True)

        # We compute new properties for the new MTG:
        for vid in MTG_to_display.vertices_iter(scale=1):
            n = MTG_to_display.node(vid)
            if n.length > 0.:
                n.exchange_surface_per_cm = n.total_exchange_surface_with_soil_solution / (n.length*100)
                n.net_sucrose_unloading_per_cm_per_day = n.net_sucrose_unloading_rate / (n.length * 100) * 60.*60.*24.

        if recording_new_MTG_files:
            # We register the new MTG there:
            with open(os.path.join(my_path,new_MTG_files_folder,filename), 'wb') as output:
                pickle.dump(MTG_to_display, output, protocol=2)
            print("The MTG file corresponding to the root system has been recorded.")

        if recording_new_MTG_properties:
            prop_file_name = os.path.join(my_path, new_MTG_properties_folder, 'root%.5d.csv')
            recording_MTG_properties(MTG_to_display, file_name=prop_file_name % ID, list_of_properties=list_of_properties)
            print("The MTG properties corresponding to the new root system have been recorded.")

        if plotting:
            # PLOTTING THE NEW MTG:
            print("Plotting...")

            # In case it has not been done so far - we define the colors in g according to a specific property:
            my_colormap(MTG_to_display,
                        property_name=property_name, vmin=vmin, vmax=vmax, lognorm=lognorm, cmap=cmap)

            # We identify the coordinates of the main seminal axis' root tip:
            vid = next(vid for vid in MTG_to_display.vertices_iter(scale=1)
                       if MTG_to_display.node(vid).axis_ID == targeted_apex_axis_ID)
            apex = MTG_to_display.node(vid)
            print("The coordinates of the apex are", apex.x2, apex.y2, apex.z2, )

            # PLOTTING WITH PYVISTA(1):
            final_image_filepath = os.path.join(my_path, images_directory, 'root%.5d.png' % ID)
            plotting_roots_with_pyvista(MTG_to_display, displaying_root_hairs=True,
                                        showing=False, recording_image=True, closing_window=True,
                                        image_file=final_image_filepath,
                                        background_color=[94, 76, 64],
                                        plot_width=600, plot_height=1600,
                                        camera_x=apex.x2 + 0.2, camera_y=apex.y2, camera_z=apex.z2 - 0.1,
                                        focal_x=apex.x2, focal_y=apex.y2, focal_z=apex.z2)
            # # PLOTTING WITH PYVISTA(2):
            # fast_plotting_roots_with_pyvista(MTG_to_display, displaying_root_hairs=True,
            #                                  showing=True, recording_image=True, closing_window=False,
            #                                  image_file=final_image_filepath,
            #                                  background_color=[94, 76, 64],
            #                                  plot_width=600, plot_height=1600,
            #                                  camera_x=apex.x2 + 0.2, camera_y=apex.y2, camera_z=apex.z2 - 0.1,
            #                                  focal_x=apex.x2, focal_y=apex.y2, focal_z=apex.z2)

    return


########################################################################################################################
########################################################################################################################

# MAIN PROGRAM:
###############

if __name__ == "__main__":

    print("Considering opening and treating recorded MTG files...")

    # PLOTTING MTG FILES:
    #####################

    # # CREATING A NEW COLORBAR:
    # # If we want to add time and colorbar:
    # # image_path = os.path.join("./", 'colobar.png')
    # im = Image.open('colorbar.png')
    # im_new = add_margin(image=im, top=3000, right=0, bottom=0, left=0, color=(0, 0, 0, 0))
    # newsize = (8000, 8000)
    # im_resized = im_new.resize(newsize)
    # im_resized.save('colorbar_new.png', quality=95)
    # # im_new.save('colorbar_new.png', quality=95)

    # # (RE-)PLOTTING ONE ORIGINAL MTG FILE:
    # loading_MTG_files(my_path='C:/Users/frees/rhizodep/saved_outputs/outputs_2024-11/Scenario_0185/',
    #                   MTG_directory="MTG_files",
    #                   opening_list=True,
    #                   # single_MTG_filename="root00599.pckl",
    #                   # list_of_MTG_ID=range(2,4318,6),
    #                   list_of_MTG_ID=[2494],
    #                   recording_images=True,
    #                   normal_plotting_with_pyvista=True, show_Pyvista_axes=False,
    #                   fast_plotting_with_pyvista=False,
    #                   closing_window=False,
    #                   factor_of_higher_resolution=2,
    #                   # property="C_hexose_root",
    #                   # vmin=1e-4, vmax=1e-3, log_scale=True, cmap='jet',
    #                   property="resp_maintenance_rate",
    #                   vmin=1e-13, vmax=1e-11, log_scale=True, cmap='jet',
    #                   # property="net_rhizodeposition_rate_per_day_per_cm",
    #                   # vmin=1e-7, vmax=1e-4, log_scale=True, cmap='jet',
    #                   # property="root_order",
    #                   # vmin=1, vmax=5, log_scale=False, cmap='jet',
    #                   # property=None,
    #                   width=800, height=800,
    #                   # width=400, height=800,
    #                   x_center=0, y_center=0, z_center=-0.20,
    #                   x_cam=0.4, y_cam=0, z_cam=-0.15,
    #                   # x_center=0, y_center=0, z_center=-0.2,
    #                   # x_cam=1.2, y_cam=0, z_cam=-0.2,
    #                   step_back_coefficient=0., camera_rotation=False, n_rotation_points=12 * 10,
    #                   background_color=[94, 76, 64],
    #                   # background_color=[255, 255, 255],
    #                   root_hairs_display=True,
    #                   mycorrhizal_fungus_display=False,
    #                   images_directory="C_hexose_image",
    #                   printing_sum=False,
    #                   recording_sum=False,
    #                   recording_g_properties=False,
    #                   # MTG_properties_folder='C:/Users/frees/rhizodep/saved_outputs/outputs_2024-05/Scenario_0163/MTG_properties/',
    #                   z_classification=False, z_min=0.00, z_max=1., z_interval=0.05, time_step_in_days=1 / 24.)
    # print("Done!")

    # # PLOTTING A SPATIAL SCALE TO PUT ON A GRAPH:
    # # We create a MTG file corresponding to the spatial scale we want to plot:
    # g = creating_a_spatial_scale_MTG(total_length=0.50, length_increment=0.1, line_thickness=0.002, starting_z=-0.1)
    # # We record the MTG:
    # g_file_name = 'C:/Users/frees/rhizodep/saved_outputs/outputs_2024-11/Scenario_0185/spatial_scale/root00000.pckl'
    # with open(g_file_name, 'wb') as output:
    #     pickle.dump(g, output, protocol=2)
    # # We plot it:
    # loading_MTG_files(my_path='C:/Users/frees/rhizodep/saved_outputs/outputs_2024-11/Scenario_0185/',
    #                   MTG_directory="spatial_scale",
    #                   opening_list=True,
    #                   recording_images=True,
    #                   normal_plotting_with_pyvista=True, show_Pyvista_axes=False,
    #                   closing_window=False,
    #                   factor_of_higher_resolution=2,
    #                   width=800, height=800,
    #                   property="length", vmin=0, vmax=0.1, log_scale=False,
    #                   x_center=0, y_center=0, z_center=-0.20,
    #                   x_cam=0.4, y_cam=0, z_cam=-0.15,
    #                   background_color=[94, 76, 64],
    #                   root_hairs_display=False,
    #                   images_directory="new_images_with_axes",
    #                   printing_sum=False,
    #                   recording_sum=False,
    #                   recording_g_properties=False,
    #                   z_classification=False)
    # print("Done!")


    # # (RE-)PLOTTING A SERIES OF ORIGINAL MTG FILES FROM ONE SCENARIO:
    # loading_MTG_files(my_path='C:/Users/frees/rhizodep/simulations/running_scenarios/outputs/Scenario_0097/',
    #                   opening_list=True,
    #                   MTG_directory="MTG_files",
    #                   list_of_MTG_ID=range(3,68),
    #                   # property="C_hexose_reserve", vmin=1e-8, vmax=1e-5, log_scale=True,
    #                   # property="net_sucrose_unloading", vmin=1e-12, vmax=1e-8, log_scale=True,
    #                   # property="net_hexose_exudation_rate_per_day_per_gram", vmin=1e-5, vmax=1e-2, log_scale=True,
    #                   # property="net_rhizodeposition_rate_per_day_per_cm", vmin=1e-8, vmax=1e-5, log_scale=True, cmap='jet',
    #                   property="C_hexose_root", vmin=1e-6, vmax=1e-3, log_scale=True, cmap='jet',
    #                   width=1200, height=1200,
    #                   x_center=0, y_center=0, z_center=-0.1, z_cam=-0.2,
    #                   camera_distance=0.4, step_back_coefficient=0., camera_rotation=False, n_rotation_points=12 * 10,
    #                   adding_images_on_plot=False,
    #                   recording_images=True,
    #                   images_directory="original_root_images",
    #                   printing_sum=False,
    #                   recording_sum=False,
    #                   recording_g_properties=False,
    #                   z_classification=False, z_min=0.00, z_max=1., z_interval=0.05, time_step_in_days=1)

    # AVERAGING MTG FILES:
    ######################

    # # CREATING NEW MTG FILES WITH AVERAGE PROPERTIES FROM DIFFERENT MTG FILES:
    # averaging_through_a_series_of_MTGs(MTG_directory='D:/Documents/MES ARTICLES/Article 2025 Rees et al PLSO/SIMULATIONS RHIZODEP/Scenario_0185/MTG_files',
    #                                    list_of_MTG_numbers_to_average=[322, 604, 897, 1178, 1394, 1550, 1707, 1875, 2037, 2188, 2340, 2494],
    #                                    odd_number_of_MTGs_for_averaging=7,
    #                                    list_of_properties=[], # We average all the properties
    #                                    recording_averaged_MTG=True,
    #                                    recording_directory='D:/Documents/MES ARTICLES/Article 2025 Rees et al PLSO/SIMULATIONS RHIZODEP/Scenario_0185/MTG_files_for_Tristan_averaged')

    # # PLOTTING THE NEW AVERAGED MTG FILES:
    # loading_MTG_files(my_path='D:/Documents/MES ARTICLES/Article 2025 Rees et al PLSO/SIMULATIONS RHIZODEP/Scenario_0185/',
    #                   opening_list=True,
    #                   MTG_directory="MTG_files_for_Tristan_averaged",
    #                   plotting_with_PlantGL=False,
    #                   normal_plotting_with_pyvista=True,
    #                   factor_of_higher_resolution=2,
    #                   closing_window=True,
    #                   background_color=[94, 76, 64],
    #                   # property="C_hexose_reserve", vmin=1e-8, vmax=1e-5, log_scale=True,
    #                   # property="net_sucrose_unloading", vmin=1e-12, vmax=1e-8, log_scale=True,
    #                   # property="net_hexose_exudation_rate_per_day_per_gram", vmin=1e-5, vmax=1e-2, log_scale=True,
    #                   # property="net_rhizodeposition_rate_per_day_per_cm", vmin=1e-8, vmax=1e-5, log_scale=True, cmap='jet',
    #                   # property="C_hexose_root", vmin=1e-6, vmax=1e-3, log_scale=True, cmap='jet',
    #                   property="hexose_consumption_by_growth_rate", vmin=1e-14, vmax=1e-10, log_scale=True, cmap='jet',
    #                   width=1200, height=1200,
    #                   x_center=0, y_center=0, z_center=-0.2,
    #                   x_cam=0.4, y_cam=0, z_cam=-0.15,
    #                   recording_images=True,
    #                   images_directory="averaged_root_images_for_Tristan",
    #                   printing_sum=False,
    #                   recording_sum=False,
    #                   recording_g_properties=False,
    #                   MTG_properties_folder='averaged_MTG_properties_for_Tristan',
    #                   z_classification=False, z_min=0.00, z_max=1., z_interval=0.05, time_step_in_days=1)
    # print("Done!")

    # PLOTTING AND COMPUTING ON ONE ROOT AXIS ONLY:
    ###############################################

    # # We load a root MTG that was previously recorded:
    # print("Loading the MTG file...")
    # filepath = 'C:/Users/frees/rhizodep/saved_outputs/root02000_142.pckl'
    # f = open(filepath, 'rb')
    # g = pickle.load(f)
    # f.close()
    #
    # # COMPUTING THE 'AXIS_ID' PROPERTY:
    # # We compute the new property "axis_ID" that gives an identifyer to each element based on the topology of the MTG:
    # print("Indexing root axes...")
    # indexing_root_MTG(g)
    # # print("Here are the values of axis_ID for the whole MTG:")
    # # print(g.properties()['axis_ID'])
    #
    # # SUBSAMPLING THE MTG:
    # # Here, we want to remove all root elements but the elements from the main seminal axis. We will therefore look for
    # # each vertex having an axis_ID beginning by "Ax1-S1-" (i.e. starting at the index 0 of the chain of characters),
    # # since all other seminal and nodal roots emerge from the first segment of the first axis.
    # # We also exclude lateral roots from the main axis by specifying a maximal number of characters allowed in axis_ID:
    # MTG_to_display = subsampling_a_MTG(g,
    #                                    string_of_axis_ID_to_remove="Ax00001-Se00001-",
    #                                    expected_starting_index_of_string = 0,
    #                                    # maximal_string_length_of_axis_ID=15,
    #                                    create_a_new_MTG = True)
    #
    # # PLOTTING THE NEW SUBSAMPLED MTG FILE:
    # print("Plotting...")
    # # In case it has not been done so far - we define the colors in g according to a specific property:
    # my_colormap(MTG_to_display,
    #             property_name="net_rhizodeposition_rate_per_day_per_cm", vmin=1e-8, vmax=1e-5, lognorm=True, cmap='jet')
    #
    # # We identify the coordinates of the main seminal axis' root tip:
    # vid = next(vid for vid in MTG_to_display.vertices_iter(scale=1)
    #            if MTG_to_display.node(vid).axis_ID == "Ax00001-Ap00000")
    # apex = MTG_to_display.node(vid)
    # print("The coordinates of the apex are", apex.x2, apex.y2, apex.z2,)
    #
    # # # > PLOTTING WITH PLANTGL:
    # # # We create the plot, by centering it on the lower end of the apex:
    # # sc = plot_mtg(MTG_to_display,
    # #               prop_cmap="C_hexose_root", lognorm=True, vmin=1e-6,vmax=1e-2, cmap='jet',
    # #               root_hairs_display=True,
    # #               mycorrhizal_fungus_display=False,
    # #               width=1200, height=800,
    # #               x_center=apex.x2, y_center=apex.y2, z_center=apex.z2,
    # #               x_cam=5.3, y_cam=5.3, z_cam=0,
    # #               displaying_PlantGL_Viewer=True,
    # #               grid_display=True)
    # # # We display the scene:
    # # pgl.Viewer.display(sc)
    # # image_name = os.path.join('C:/Users/frees/rhizodep/saved_outputs/', 'plot.png')
    # # pgl.Viewer.saveSnapshot(image_name)
    #
    # # > PLOTTING WITH PYVISTA:
    # fast_plotting_roots_with_pyvista(MTG_to_display, displaying_root_hairs=True,
    #                                  showing=True, recording_image=True, closing_window=False,
    #                                  image_file='C:/Users/frees/rhizodep/saved_outputs/plot_with_pyvista.png',
    #                                  background_color=[94, 76, 64],
    #                                  plot_width=600, plot_height=1600,
    #                                  camera_x=apex.x2+0.2, camera_y=apex.y2, camera_z=apex.z2-0.1,
    #                                  focal_x=apex.x2, focal_y=apex.y2, focal_z=apex.z2)

    # PLOTTING ONLY ONE AXIS:

    # property_name = "net_rhizodeposition_rate_per_day_per_cm"
    # vmin = 1e-8
    # vmax = 1e-4
    # lognorm = True

    # property_name = "total_net_rhizodeposition"
    # vmin = 1e-12
    # vmax = 1e-9
    # lognorm = True

    # property_name = "net_sucrose_unloading_rate"
    # vmin = 1e-14
    # vmax = 1e-11
    # lognorm = True

    # property_name = "net_unloading_rate_per_day_per_cm"
    # vmin = 1e-8
    # vmax = 1e-4
    # lognorm = True

    # property_name = "root_exchange_surface_per_cm"
    # vmin = 1e-4
    # vmax = 8e-4
    # lognorm = False

    # list_of_MTG = [30*24, 60*24, 90*24, 120*24, 150*24]
    # list_of_MTG = list(range(30*24-4,30*24+4)) + list(range(60*24-4,60*24+4)) + list(range(90*24-4,90*24+4)) + list(range(120*24-4,120*24+4)) + list(range(150*24-4,150*24+4))
    # list_of_MTG = list(range(0, 24))

    # showing_one_axis(my_path='outputs/Scenario_0001/',
    #                  opening_list=True,
    #                  file_extension='pckl',
    #                  MTG_directory="MTG_files",
    #                  # file_extension='csv',
    #                  # MTG_directory="MTG_properties",
    #                  list_of_MTG_ID=list_of_MTG,
    #                  # starting_string_of_axes_to_remove="Ax00001-Se00001-",
    #                  targeted_apex_axis_ID="Ax00001-Ap00000",
    #                  maximal_string_length_of_axis_ID=-1, # Here we consider all lateral roots
    #                  # maximal_string_length_of_axis_ID=15, # Here we select only the elements on the main axis, not the lateral ones
    #                  recording_new_MTG_files=False,
    #                  # new_MTG_files_folder=os.path.join('axis_MTG_files'),
    #                  recording_new_MTG_properties = False,
    #                  # new_MTG_properties_folder = os.path.join('axis_85-95_days_MTG_properties'),
    #                  plotting=True,
    #                  # property_name="net_rhizodeposition_rate_per_day_per_cm",
    #                  # vmin=1e-8, vmax=1e-5, lognorm=True, cmap='jet',
    #                  # property_name="C_hexose_root",
    #                  # vmin=1e-6, vmax=1e-3, lognorm=True, cmap='jet',
    #                  # property_name="total_exchange_surface_with_soil_solution",
    #                  # vmin=5e-5, vmax=3.5e-4, lognorm=False, cmap='jet',
    #                  property_name=property_name,
    #                  # vmin=1e-4, vmax=8e-4, lognorm=False, cmap='jet',
    #                  # property_name="net_sucrose_unloading_per_cm_per_day",
    #                  # vmin=1e-9, vmax=1e-5, lognorm=True, cmap='jet',
    #                  vmin=vmin, vmax=vmax, lognorm=lognorm, cmap='jet',
    #                  images_directory="axis_55-65_days_images"
    #                  )

    # # COMPUTING PROPERTIES ON DIFFERENT CLASSES OF ROOTS:
    # #####################################################
    #
    # loading_MTG_files(my_path='C:/Users/frees/rhizodep/saved_outputs/outputs_2024-11/Scenario_0185/',
    #                   opening_list=True,
    #                   MTG_directory="MTG_files",
    #                   list_of_MTG_ID=[740,741],
    #                   file_extension='pckl',
    #                   plotting_with_PlantGL=False,
    #                   normal_plotting_with_pyvista=False,
    #                   fast_plotting_with_pyvista=False,
    #                   computing_on_different_roots=True, comparing_distance_from_tip=True, distance_treshold=0.04,
    #                   properties_to_compute=["total_net_rhizodeposition",
    #                                          "net_rhizodeposition_rate_per_day_per_cm",
    #                                          "length",
    #                                          "total_exchange_surface_with_soil_solution"],
    #                   summing_different_roots=True, averaging_different_roots=True,
    #                   printing_sum=False,
    #                   recording_sum=False,
    #                   printing_warnings=True,
    #                   recording_g_properties=False)

    # # RECALCULATING THE Z CLASSIFICATION ON THE LAST MTG FILE:
    # loading_MTG_files(my_path='C:/Users/frees/rhizodep/saved_outputs/outputs_2024-11/Scenario_0185/',
    #                   MTG_directory="MTG_files",
    #                   opening_list=False,
    #                   single_MTG_filename="root04318.pckl",
    #                   # list_of_MTG_ID=range(2,4318,6),
    #                   list_of_MTG_ID=[1920],
    #                   recording_images=False,
    #                   # normal_plotting_with_pyvista=True, show_Pyvista_axes=False,
    #                   # fast_plotting_with_pyvista=False,
    #                   # closing_window=False,
    #                   # factor_of_higher_resolution=2,
    #                   # property="C_hexose_root",
    #                   # vmin=1e-4, vmax=1e-3, log_scale=True, cmap='jet',
    #                   # property="resp_maintenance_rate",
    #                   # vmin=1e-13, vmax=1e-11, log_scale=True, cmap='jet',
    #                   # property="net_rhizodeposition_rate_per_day_per_cm",
    #                   # vmin=1e-7, vmax=1e-4, log_scale=True, cmap='jet',
    #                   # property="root_order",
    #                   # vmin=1, vmax=5, log_scale=False, cmap='jet',
    #                   # property=None,
    #                   # width=800, height=800,
    #                   # width=400, height=800,
    #                   # x_center=0, y_center=0, z_center=-0.20,
    #                   # x_cam=0.4, y_cam=0, z_cam=-0.15,
    #                   # x_center=0, y_center=0, z_center=-0.2,
    #                   # x_cam=1.2, y_cam=0, z_cam=-0.2,
    #                   # step_back_coefficient=0., camera_rotation=False, n_rotation_points=12 * 10,
    #                   # background_color=[94, 76, 64],
    #                   # background_color=[255, 255, 255],
    #                   # root_hairs_display=True,
    #                   # mycorrhizal_fungus_display=False,
    #                   # images_directory="C_hexose_image",
    #                   printing_sum=True,
    #                   recording_sum=False,
    #                   recording_g_properties=False,
    #                   # MTG_properties_folder='C:/Users/frees/rhizodep/saved_outputs/outputs_2024-11/Scenario_0185/MTG_properties/',
    #                   z_classification=True, z_min=0.00, z_max=1., z_interval=0.05, time_step_in_days=1 / 24.)
    # print("Done!")