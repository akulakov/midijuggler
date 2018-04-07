# import the necessary packages
from __future__ import print_function
from imutils.video import WebcamVideoStream
from imutils.video import FPS
import argparse
import imutils
import cv2
import colorsys
import math
from math import hypot
import time #for sending midi
import rtmidi #for sending midi
import numpy as np #for webcam
import cv2 #for webcam
from collections import deque # for tracking balls
import argparse # for tracking balls
import imutils # for tracking balls
import sys # for tracking balls
import pyautogui
from scipy import ndimage
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pygame as pg
from datetime import datetime
from datetime import timedelta
from random import randint
import random
import scipy.stats as ss
import threading as th
from music_helper import get_notes_in_scale
from plot_helper import create_plots
pg.mixer.pre_init(frequency=44100, size=-16, channels=1, buffer=512)
pg.mixer.init()
pg.init()
pg.mixer.set_num_channels(19)
column_sounds = [pg.mixer.Sound("hhat2.wav"), pg.mixer.Sound("snare.wav")]
show_camera = False
record_video = False
show_mask = True
show_overlay = False
all_mask = []
video_name = "3Bshower.avi"
increase_fps = True
show_time = False
use_adjust_song_magnitude = False
play_peak_notes = True
print_peaks = True                                    
using_midi = True
using_height_as_magnitude = True    
duration = 40 #seconds
average_min_height = 30
peak_count,midiout = 0,rtmidi.MidiOut()
midi_associations = {}
all_cx,all_cy,all_vx,all_vy,all_ay,last_peak_time,peak_count = [[0]],[[0]],[[0]],[[0]],[[0]],[-.25]*20,0
path_type, path_phase, notes_in_scale_count = [""]*20,[""]*20,len(get_notes_in_scale("C",[3,4],"NATURAL_MINOR",1))
midi_note_based_on_position_is_in_use = False
def frames_are_similar(image1, image2):
    return image1.shape == image2.shape and not(np.bitwise_xor(image1,image2).any())
rotating_sound_num = 0
def midi_controller_value_from_positions(current_position, max_position, edge_buffer):
    value = 0
    if current_position<edge_buffer:
        value = 127
    elif current_position>max_position-edge_buffer:
        value = 0
    else:
        value = int(127*((current_position-edge_buffer)/(max_position-edge_buffer*2)))
    return value
def rotating_midi_note(index, list_of_notes):
    global rotating_sound_num
    skip_random_note = True    
    rotating_sound_num = rotating_sound_num + 1
    if skip_random_note:
        if random.randint(0,100) < 20:
            rotating_sound_num = rotating_sound_num + 1
    if rotating_sound_num >= len(list_of_notes):
        rotating_sound_num = 0
    return list_of_notes[rotating_sound_num]
def midi_note_based_on_position(index, list_of_notes):
    midi_note_based_on_position_is_in_use = True
    rounded_to_scale = True
    max_position = frame_width
    notes_to_return = []
    if rounded_to_scale:
        stretched_note_positions = []
        stretched_note_positions_indices = [] 
        section_size = max_position/len(list_of_notes)
        for i in range(0,len(list_of_notes)):
            stretched_note_positions.append(int(i*section_size))
            stretched_note_positions_indices.append(i)            
        closest_stretched_note = min(stretched_note_positions, key=lambda x:abs(x-all_cx[index][-1]))
        notes_to_return = list_of_notes[stretched_note_positions.index(closest_stretched_note)]
    else:
        notes_to_return = midi_controller_value_from_positions(all_cx[index][-1],max_position,0)       
    return notes_to_return 
def midi_magnitude(index):
    return 112
def midi_modulator(index, type, channel, controller_num):
    value = 0
    if type == "width":
        value = midi_controller_value_from_positions(all_cx[index][-1],frame_width,0)
    if type == "height":
        value = midi_controller_value_from_positions(all_cy[index][-1],480,0)
    return [channel, controller_num, value]
def create_association_object():
    cross_note = [rotating_midi_note, get_notes_in_scale("C",[5,6],"MAJOR",5)]
    column_note = [rotating_midi_note, get_notes_in_scale("D",[2,3],"MELODIC_MINOR",5)]
    midi_associations["peak"] = {}
    midi_associations["peak"]["mid column"] = {}
    midi_associations["peak"]["mid column"]["channel"] = 2
    midi_associations["peak"]["mid column"]["note"] = column_note
    midi_associations["peak"]["mid column"]["magnitude"] = midi_magnitude
    #midi_associations["peak"]["mid column"]["modulator"] = [["width",0,0], ["height",0,1]]    
    midi_associations["peak"]["left column"] = {}
    midi_associations["peak"]["left column"]["channel"] = 2
    midi_associations["peak"]["left column"]["note"] = column_note
    midi_associations["peak"]["left column"]["magnitude"] = midi_magnitude
    #midi_associations["peak"]["left column"]["modulator"] = [["width",0,0], ["height",0,1]]    
    midi_associations["peak"]["right column"] = {}
    midi_associations["peak"]["right column"]["channel"] = 2
    midi_associations["peak"]["right column"]["note"] = column_note
    midi_associations["peak"]["right column"]["magnitude"] = midi_magnitude
    #midi_associations["peak"]["right column"]["modulator"] = [["width",0,0], ["height",0,1]]    
    midi_associations["peak"]["mid cross"] = {}
    midi_associations["peak"]["mid cross"]["channel"] = 2
    midi_associations["peak"]["mid cross"]["note"] = cross_note
    midi_associations["peak"]["mid cross"]["magnitude"] = midi_magnitude
    #midi_associations["peak"]["mid cross"]["modulator"] = [["width",0,0], ["height",0,1]]    
    midi_associations["peak"]["left cross"] = {}
    midi_associations["peak"]["left cross"]["channel"] = 2
    midi_associations["peak"]["left cross"]["note"] = cross_note
    midi_associations["peak"]["left cross"]["magnitude"] = midi_magnitude
    #midi_associations["peak"]["left cross"]["modulator"] = [["width",0,0], ["height",0,1]]    
    midi_associations["peak"]["right cross"] = {}
    midi_associations["peak"]["right cross"]["channel"] = 2
    midi_associations["peak"]["right cross"]["note"] = cross_note
    midi_associations["peak"]["right cross"]["magnitude"] = midi_magnitude
    #midi_associations["peak"]["right cross"]["modulator"] = [["width",0,0], ["height",0,1]]
def set_up_midi():
    #midiout = rtmidi.MidiOut()
    available_ports = midiout.get_ports()
    if available_ports:
        midiout.open_port(1)
    else:
        midiout.open_virtual_port("My virtual output")
def set_up_peak_notes():
    sounds = []
    sounds.append(pg.mixer.Sound("notes01.wav"))
    sounds.append(pg.mixer.Sound("notes02.wav"))
    sounds.append(pg.mixer.Sound("notes03.wav"))
    sounds.append(pg.mixer.Sound("notes04.wav"))
    return sounds
def set_up_record_camera(video_name):        
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    return cv2.VideoWriter(video_name,fourcc, 20.0, (frame_width,frame_height))
def set_up_adjust_song_magnitude():
    pg.mixer.pre_init(frequency=44100, size=-16, channels=1, buffer=512)
    pg.mixer.init()
    pg.init()
    pg.mixer.set_num_channels(19)
    song=pg.mixer.Sound("song.wav")
    song.play()
    return song
def do_arguments_stuff():
    PY3 = sys.version_info[0] == 3
    if PY3:#find out if this stuff is needed or not
        xrange = range
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--video",
            help="path to the (optional) video file")
    ap.add_argument("-b", "--buffer", type=int, default=64,
            help="max buffer size")
    args = vars(ap.parse_args())
    pts = deque(maxlen=args["buffer"])   
    return args
def set_up_camera():
    if increase_fps:
        vs = WebcamVideoStream(src=0).start()
    if play_peak_notes:
        sounds = set_up_peak_notes()
    else:
        sounds = None
    if use_adjust_song_magnitude:
        song = set_up_adjust_song_magnitude()
    else:
        song = None
    if using_midi:
        set_up_midi()
    args = do_arguments_stuff()#i dont know what this is, maybe it is garbage?
    if record_video:
        out = set_up_record_camera(video_name)
    else:
        out = None
    return vs, sounds, song, args, out
def analyze_video(start,loop_count,vs,camera,args,frame_count):
    global frame_height, frame_width
    if time.time()-start > 0:
        fps = frame_count/(time.time()-start)
    else:
        fps = 10
    if increase_fps:
        frame = vs.read()
        grabbed = None
    else:
        grabbed, frame = camera.read()
    frame_height, frame_width, channels = frame.shape
    loop_count = loop_count + 1
    break_for_no_video = False
    if args.get("video") and not grabbed:
        break_for_no_video = True 
    return fps, grabbed, frame, loop_count, break_for_no_video    
def get_contours(frame, contour_count_window, fps):    
    framehsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_range = np.array([0, 0, 247])
    upper_range = np.array([146, 12, 255])     
    original_mask = cv2.inRange(framehsv, lower_range, upper_range)
    erode_kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(2,2))
    dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(4,4))
    mask = cv2.erode(original_mask, erode_kernel, iterations=3)
    mask = cv2.dilate(mask, dilate_kernel, iterations=3)
    im2, contours, hierarchy = cv2.findContours(mask,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        contour_count_window.append(len(contours))        
    else:
        contour_count_window.append(0)
    return contours, mask, original_mask, contour_count_window
def get_contour_centers(contours, average_contour_count,min_height_window):
    global average_min_height
    cx,cy,moments,min_height,maxM00,maxIndex = [],[],[],100000,0,-1
    for i in range(0,len(contours)):
        contour = contours[i]
        M = cv2.moments(contour) 
        if M['m00'] > 0:
            cx.append(int(M['m10']/M['m00']))
            cy.append(int(M['m01']/M['m00']))
            if M['m00'] > maxM00:
                maxM00 = M['m00']
                maxIndex = i
            x,y,w,height = cv2.boundingRect(contour)
            if height < min_height:
                min_height = height
    min_height_window.append(min_height)
    average_min_height = sum(min_height_window)/len(min_height_window)            
    return cx,cy, maxIndex, min_height_window
def calculate_velocity(last_two_positions):
    return last_two_positions[1] - last_two_positions[0]
def calculate_acceleration(last_two_velocities):    
    return last_two_velocities[1] - last_two_velocities[0]
def calculate_kinematics():
    last_two_cx,last_two_cy = [t[-2:] for t in all_cx],[t[-2:] for t in all_cy]             
    for i in range(0,len(all_cx)):
        if len(last_two_cx[i]) > 1:
            all_vx[i].append(calculate_velocity(last_two_cx[i]))
            all_vy[i].append(calculate_velocity(last_two_cy[i]))
            if len(all_vx[i]) > 2:
                all_ay[i].append(calculate_acceleration([all_vy[i][-2],all_vy[i][-1]]))
            else:
                all_ay[i].append(0)
        else:
            all_vx[i].append(0)
            all_vy[i].append(0)
    return all_vx,all_vy,all_ay
#def predicted_point():
#def high_throw_or_drop_seen(cx, cy,average_contour_count,last_second_of_all_cx,last_second_of_all_cy,missing_ball_count):
    #for i in range(0,len(last_second_of_all_cx)):
        #if predicted_point(last_second_of_all_cx[i][-3:]) < 0 or predicted_point(last_second_of_all_cx[i][-3:]) > width
        #we want check to see if each ball was heading towards a drop edge, or the top edge,
        #   we want to deal with those 2 things differently, and if neither is happening then we want to just return our
        #   variables as we got them.
        #However, if a ball was heading toward an edge then we want to deal with it accordingly:
        #   top edge:
        #       predict when it will peak, or maybe set up a loop that lasts through several frames that
        #       tells where the contour would have been if the camera could see it and sets a cx/cy based on it until
        #       it gets back on the screen and reduces the missing_ball_count by 1
        #   drop edge:
        #       it drops the average number of balls down 1 and reduces the missing_ball_count by 1
    #return cx, cy, average_contour_count, missing_ball_count 
#def split_contour():
    #nothing = "everything"
    #this is what we do once we know that no ball has left the screen, but we still have too few balls,
def split_contours(max_contour_index,cx,cy,average_contour_count,last_cx,last_cy,missing_ball_count):
    #cx,cy,average_contour_count,missing_ball_count=high_throw_or_drop_seen(cx,cy,average_contour_count,last_second_of_all_cx,last_second_of_all_cy,missing_ball_count)
    #for i in range(0,missing_ball_count):
    temp_distances_to_max_contour = find_distances([cx[max_contour_index]],[cy[max_contour_index]],last_cx,last_cy)
    distances_to_max_contour = []
    for i in range(0, len(temp_distances_to_max_contour)):
        distances_to_max_contour.append(temp_distances_to_max_contour[i][0])
    distances_to_max_contour = np.asarray(distances_to_max_contour)
    blob_contour_indices = distances_to_max_contour.argsort()[:2]
    predicted_cx_1 = all_vx[blob_contour_indices[0]][-1] + all_cx[blob_contour_indices[0]][-1]
    predicted_cx_2 = all_vx[blob_contour_indices[1]][-1] + all_cx[blob_contour_indices[1]][-1]
    predicted_cy_1 = all_vy[blob_contour_indices[0]][-1] + .5*all_ay[blob_contour_indices[0]][-1]**2 + all_cx[blob_contour_indices[0]][-1]
    predicted_cy_2 = all_vy[blob_contour_indices[1]][-1] + .5*all_ay[blob_contour_indices[1]][-1]**2 + all_cx[blob_contour_indices[1]][-1]
    last_min_1 = min(all_cy[blob_contour_indices[0]][min(100, -len(all_cy[blob_contour_indices[0]])):])
    last_min_2 = min(all_cy[blob_contour_indices[1]][min(100, -len(all_cy[blob_contour_indices[1]])):])
    print(last_min_1)
    print(last_min_2)
    predicted_cy_1 = min(last_min_1, predicted_cy_1)
    predicted_cy_2 = min(last_min_2, predicted_cy_2)
    cx[max_contour_index],cy[max_contour_index] = predicted_cx_1,predicted_cy_1
    cx.append(predicted_cx_2)
    cy.append(predicted_cy_2)
    print("done predicting")
    print(cx)
    print(cy)
    return cx, cy
def find_distances(cx,cy):
    distances = []
    for i in range(0,len(all_cx)):
        distances.append([])
        for j in range(0,len(cx)):
            dist = math.sqrt( (cx[j] - all_cx[i][-1])**2 + (cy[j] - all_cy[i][-1])**2 )
            distances[i].append(dist)
    return distances
def get_contour_matchings(distances,average_contour_count): 
    min_dist_row = 0
    min_dist_col = 0
    indices_to_return = [0]
    for i in range(1,average_contour_count):
        indices_to_return.append(i)
    min_dist = 100000
    for t in range(0,average_contour_count):
        for i in range(0,len(distances)):
            for j in range(0,len(distances[0])):                
                if distances[i][j] <= min_dist:
                    min_dist = distances[i][j]
                    min_dist_row = i
                    min_dist_col = j
        if min_dist_row < len(indices_to_return):
            indices_to_return[min_dist_row] = min_dist_col
        min_dist = 100000
        for i in range(len(distances[min_dist_row])):
            distances[min_dist_row][i] = 100000
        for d in range(0,len(distances)):
            distances[d][min_dist_col] = 100000  
    return indices_to_return, len(indices_to_return)
def connect_contours_to_histories(matched_indices,cx,cy):            
    while len(all_cx) < len(matched_indices):
        all_cx.append([]*len(all_cx[0]))
        all_cy.append([]*len(all_cx[0]))
        all_vx.append([]*len(all_cx[0]))
        all_vy.append([]*len(all_cx[0]))
        all_ay.append([]*len(all_cx[0]))
    for i in range(0,len(matched_indices)):
        all_cx[i].append(cx[matched_indices[i]])
        all_cy[i].append(cy[matched_indices[i]])
def average_position(all_axis, window_length, window_end_frame):
    average_pos = 0
    count = 0
    average_duration = min(len(all_axis[0]), window_length)
    for i in range(0, len(all_axis)):
        for j in range(0, average_duration):
            index = window_end_frame-j
            if abs(index)<len(all_axis[i]):
                if all_axis[i][-index] > 0:
                    count = count+1
                    average_pos = average_pos + all_axis[i][index]
    if count > 0:
        average_pos = average_pos/count
    return average_pos
def determine_relative_positions(match_indices_count):
    last_cx,last_cy = [j for i in [t[-1:] for t in all_cx] for j in i],[j for i in [t[-1:] for t in all_cy] for j in i]
    last_cx = last_cx[0:match_indices_count]
    last_cy = last_cy[0:match_indices_count]
    relative_positions = []
    ranked_list_x = ss.rankdata(last_cx)
    ranked_list_y = ss.rankdata(last_cx)
    for i in range(0,len(last_cx)):
        if ranked_list_x[i] == min(s for s in ranked_list_x):
            relative_positions.append("left")
        elif ranked_list_x[i] == max(s for s in ranked_list_x):
            relative_positions.append("right")
        else:
            relative_positions.append("mid")
    return relative_positions
def ball_at_peak(vy_window):
    global peak_count
    number_of_frames_up = 4 
    vy_window = vy_window[-(number_of_frames_up):]    
    if all(j > 0 for j in vy_window[-4:-1]) and vy_window[-1] <= 0 and abs(sum(vy_window[-4:-1])/3)>4:
        peak_count = peak_count+1
        return True
    else:
        return False
def peak_checker(index):
    at_peak = False
    min_peak_period = .4
    if len(all_vy[index]) > 2:
        if time.time()-last_peak_time[index] > min_peak_period:
            if ball_at_peak(all_vy[index]) and time.time() - last_peak_time[index] > .5:
                last_peak_time[index] = time.time()
                at_peak = True
    return at_peak
def catch_detected(index):
    number_of_frames_up = 4 
    vy_window = all_vy[index][-(number_of_frames_up):]
    if all(j < 0 for j in vy_window[-4:-1]) and vy_window[-1] >= 0:
        #print("catch!")
        return True
    else:
        return False
def throw_detected(index):
    number_of_frames_up = 3
    vy_window = all_vy[index][-(number_of_frames_up):]
    if all(j > 0 for j in vy_window[-2:]) and vy_window[0] <= 0:
        return True
    else:
        return False
def determine_path_phase(index):
    if len(all_vy[index]) > 0:
        if path_phase[index] == "peak" and all_vy[index][-1] < 0:
            path_phase[index] = "down"
        if peak_checker(index):
            path_phase[index] = "peak"       
        if path_phase[index] == "catch":        
            path_phase[index] = "held"
        if path_phase[index] == "down" and catch_detected(index):
            path_phase[index] = "catch"        
        if path_phase[index] == "throw" and all_vy[index][-1] > 0:
            path_phase[index] = "up"
        if throw_detected(index):
            path_phase[index] = "throw"
def determine_path_type(index,position):
    path_type[index] = position
    if abs(all_vx[index][-1]) > average_min_height/5:
        path_type[index] = path_type[index] + ' cross'
    else:
        path_type[index] = path_type[index] + ' column'
    #if abs(xv) > average_min_height and abs(yv) < average_min_height:
        #path_type[index] = 'one'
def analyze_trajectory(index,relative_position):
    if len(all_vx[index]) > 0:
        determine_path_phase(index)
        determine_path_type(index,relative_position)   
def get_midi_note(index):
    #print(str(path_phase) + " | " +str(path_type))
    channel = 0
    note = 0
    magnitude = 0
    #print(path_phase)
    #print(path_type)
    this_path_phase = path_phase[index]
    this_path_type = path_type[index]
    if this_path_phase in midi_associations:
        if this_path_type in midi_associations[this_path_phase]:
            if 'channel' in midi_associations[this_path_phase][this_path_type]:
                channel = midi_associations[this_path_phase][this_path_type]["channel"]           
            if 'note' in midi_associations[this_path_phase][this_path_type]:
                this_association = midi_associations[this_path_phase][this_path_type]["note"]
                notes = this_association[0](index,this_association[1])
            if 'magnitude' in midi_associations[this_path_phase][this_path_type]:
                magnitude = midi_associations[this_path_phase][this_path_type]["magnitude"](index)    
    return channel, notes, magnitude
def get_midi_modulation(index):
    this_path_phase = path_phase[index]
    this_path_type = path_type[index]
    modulators = []
    if this_path_phase in midi_associations:
        if this_path_type in midi_associations[this_path_phase]:
            if 'modulator' in midi_associations[this_path_phase][this_path_type]:
                for i in midi_associations[this_path_phase][this_path_type]['modulator']:
                    modulators.append(midi_modulator(index, i[0], i[1], i[2]))
    return modulators
def send_midi_messages(channel, notes, magnitude, modulators):
    for i in modulators:
        send_midi_cc(i[0],i[1],i[2])
    for n in notes:
        send_midi_note(channel,n,magnitude)
def get_wav_sample(index):
    note = 1
    return note, magnitude
def get_wav_modulation(index):
    modulation = 1
    return modulation
def send_wav_messages(note, magnitude, modulation):
    nothing = 0
def create_audio(index):
    if using_midi:
        if path_phase[index] in midi_associations:
            if path_type[index] in midi_associations[path_phase[index]]:
                channel, notes, magnitude = get_midi_note(index)         
                modulators = get_midi_modulation(index)
                send_midi_messages(channel, notes, magnitude, modulators)
    else:
        note, magnitude = get_wav_sample(index)
        modulation = get_wav_modulation(index)
        send_wav_messages(note, magnitude, modulation)      
def midi_note_channel_num(channel,on_or_off):
    if on_or_off == 'on':
        i = int('0x90', 16)
    elif on_or_off == 'off':     
        i = int('0x80', 16)     
    i += int(channel)
    return i
def midi_cc_channel_num(channel):
    i = int('0xB0', 16)
    i += int(channel)
    return i
midi_channel_to_off = 0
midi_note_to_off = 0
def send_midi_note_on_only(channel,note,magnitude):
    note_on = [midi_note_channel_num(channel,'on'), note, magnitude]    
    midiout.send_message(note_on)
def turn_midi_note_off(channel,note):
    note_off = [midi_note_channel_num(channel,'off'), note, 0]
    try:
        midiout.send_message(note_off)
    except:
        pass
def send_midi_note(channel,note,magnitude):                          
    note_on = [midi_note_channel_num(channel,'on'), note, magnitude]
    midiout.send_message(note_on)
    midi_channel_to_off = channel
    midi_note_to_off = note
    off = th.Timer(0.4,turn_midi_note_off, args = [channel,note])     
    off.start()
def use_as_midi_signal(current_num,max_num):
    return 127*(current_num/max_num)
def send_midi_cc(channel,controller_num,value):
    send_cc = [midi_cc_channel_num(channel), controller_num, value]
    midiout.send_message(send_cc)
def adjust_song_magnitude(axis,edge_buffer,position,song):
    if axis == "y":
        size = frame_height        
    if axis == "x":
        size = frame_width
    if position<edge_buffer:
        song.set_magnitude(1)
    if position>frame_height-edge_buffer:
        song.set_magnitude(0)
    song.set_magnitude((position-edge_buffer)/(size-edge_buffer*2))
def create_grid_of_notes(mask_copy,matched_indices_count):
    global path_type
    mask_copy=cv2.cvtColor(mask_copy,cv2.COLOR_GRAY2BGR)
    rectangle_width = int(frame_width/max(1,notes_in_scale_count))
    rectangles_with_peaks = []
    rectangles_with_peaks_path_types = []
    for i in range(0,matched_indices_count):
        if path_phase[i] == 'peak':
            rectangles_with_peaks.append(math.floor(all_cx[i][-1]/rectangle_width))
            rectangles_with_peaks_path_types.append(path_type[i])  
    for i in range(0,notes_in_scale_count):
        left_corner = i*rectangle_width
        right_corner = (i+1)*rectangle_width
        if i in rectangles_with_peaks:
            this_path_type = rectangles_with_peaks_path_types[rectangles_with_peaks.index(i)]
            fill_blue,fill_green,fill_red = 0,0,0
            if 'cross' in this_path_type:
                fill_red = 0
            if 'column' in this_path_type:
                fill_blue,fill_green,fill_red = 100,100,200
            if 'right' in this_path_type:
                fill_blue = 255
            if 'left' in this_path_type:
                fill_green = 255
            if 'mid' in this_path_type:
                fill_red = 255
            cv2.rectangle(mask_copy,(left_corner,0),(right_corner,frame_height),(fill_blue,fill_green,fill_red),thickness=cv2.FILLED)
        else:
            cv2.rectangle(mask_copy,(left_corner,0),(right_corner,frame_height),(255,255,255),2)
    return mask_copy
def show_and_record_video(frame,out,start,fps,mask,all_mask,original_mask,matched_indices_count):    
    show_scale_grid = True            
    if record_video:
        record_frame(frame, out, start, fps)
    if show_camera:
        cv2.imshow('Frame', frame)
    if show_mask:
        if show_scale_grid:# and midi_note_based_on_position_is_in_use:
            mask_copy = mask
            mask_copy = create_grid_of_notes(mask_copy,matched_indices_count)
            mask_copy = cv2.flip(mask_copy,1)
            cv2.imshow('mask',mask_copy)
        else:
            cv2.imshow('mask',mask)
    if show_overlay: 
        all_mask.append(original_mask)
    return all_mask
def record_frame(frame, out, start, fps):    
    if fps>20:
        fpsdif = fps/20 #20 is the fps of our avi
        if randint(0, 100)<fpsdif*10: #this random is used to keep our video from having too many frames and playing slow
            out.write(frame)
    else:
        for i in range(math.floor(20/fps)):
            out.write(frame)
        if randint(0, 100)<((20/fps)-math.floor(20/fps)*100):
            out.write(frame)
def should_break(start,break_for_no_video):      
    what_to_return = False
    if time.time() - start > duration or break_for_no_video:
        what_to_return = True
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):            
        what_to_return = True
    return what_to_return
def closing_operations(fps,vs,camera,out,all_mask):
    global midiout
    print("fps: "+str(fps))
    print("peaks: "+str(peak_count))
    if using_midi:
        del midiout
    if increase_fps:
        vs.stop()
    camera.release()
    if record_video:
        out.release()
    cv2.destroyAllWindows()
    if show_overlay:        
        cv2.imshow('overlay',sum(all_mask))
    return time.time()   
def run_camera():
    global all_mask,all_cx,all_cy,all_vx,all_vy,all_ay
    camera = cv2.VideoCapture(0)
    vs, sounds, song, args, out = set_up_camera()
    start,loop_count,num_high = time.time(),0,0
    at_peak, break_for_no_video = [-.25]*20,False
    contour_count_window, min_height_window,old_frame,frame_count = deque(maxlen=120), deque(maxlen=60), None, 0
    while True:
        fps, grabbed, frame, loop_count, break_for_no_video = analyze_video(start,loop_count,vs,camera,args,frame_count)
        if loop_count>1 and frames_are_similar(frame, old_frame):
            continue
        else:
            frame_count = frame_count+1
        old_frame,matched_indices_count = frame,0
        contours, mask, original_mask, contour_count_window = get_contours(frame,contour_count_window,fps)
        if contours and frame_count > 10:
            average_contour_count = round(sum(contour_count_window)/len(contour_count_window)) 
            cx, cy, max_contour_index, min_height_window = get_contour_centers(contours,average_contour_count,min_height_window)            
            calculate_kinematics()             
            distances = find_distances(cx,cy)               
            matched_indices,matched_indices_count = get_contour_matchings(distances,min(len(contours),average_contour_count))
            connect_contours_to_histories(matched_indices,cx,cy)
            relative_positions = determine_relative_positions(len(matched_indices))
            for i in range(0,len(matched_indices)):                
                analyze_trajectory(i,relative_positions[i])
                create_audio(i)
            if use_adjust_song_magnitude:
                adjust_song_magnitude("y",120,average_position(all_cy, 10, -1),song)
        all_mask = show_and_record_video(frame,out,start,fps,mask,all_mask,original_mask,matched_indices_count)               
        if should_break(start,break_for_no_video):
            break
    end = closing_operations(fps,vs,camera,out,all_mask)
    create_plots(frame_count,start,end,all_cx,all_cy,frame_height)
create_association_object()
run_camera()
    #NEXT:
    #look into the color selector code for choosing the color to track
    #chosen from the scale can be a chosen number of random notes
    #   it cycles through these notes a chosen number of times, and then cycles through another set based on a chosen pattern on repeat,
    #       for instance, with 4 random notes, [1,1,2] might play: C,D,A,G , C,D,A,G , D,B,C,D , C,D,A,G , C,D,A,G , D,B,C,D
    #look into the pychord library, maybe there is something useful there
    #get the wav stuff caught up to the midi stuff as much as possible, there are some really short piano notes in a folder
    #   get an octave or two of a few different instruments
    #keep putting instructions into the readme, need stuff about REAPER, loopbe, iac or whatever mac uses
    #Pip freeze may help make it easier for others to use
    #Look into making an exe from python
#for now we can just ignore the issue of dictionary key for [all]

#6 path types
#   right cross
#   left cross
#   left column
#   right column
#   non-end column
#   one

#all path types have all the path phases, except 'one', it only has its path straight across

#phase of path
#   thrown
#   way up
#   peak
#   way down
#   catch
#   all phases

#new juggling coordinate to use 
#   average peak height, average hand catch height

#relattive position
#odd even one
#synched peaks
#x, y of each ball, average of all balls,
#largest distance between two contours
#   shortest distance between two contours
#   equadistance of all contours
#velocity at throw, maybe an average velocity over course of path
#lift and held(left,right,both)
#   binary on off switch
#changed height by hand

#MUSIC---------
#pitch
#magnitude
#tempo
#filters
#mute
#solo
#trigger sample
#start/stop loop
#single note, multiple notes
#notes in a cycle
#   notes in a scale
#       prechosen number of notes from a scale.
#           selecting the scale
#               selecting key of the scale
#       randomized notes in a scale
#       randomized skipped notes in a scale
#   preset notes in a scale, with some notes missing with a randomizer
#preselected chords or chord progressions
#   preselected chords for individual actions
#   cycling through chords in a chord progression
#       cycle by throws
#               detects tempo and then counts measures for which a given chord will be played for any throw
#       cycle by beats
#select instrument for action

#transport actions, play, pause,stop,loop
#sound modulation
#note creation

#you can set your sequence by selecting your chord types(major, major 7, minor, minor 7) and chord root(the notes, c, c#)
#   in this same way you have a scale type(minor,major) and a scale root(or key)

        #   count number of globs without dialation, maybe there will be enough indication from little contours
        #       in between fingers
        #there are 2 hardcoded 'deque(maxlen=30), their maxlen should be changed to being dynamically set from fps
        #   figure out what 'contour_count_window.extend' does exactly, maybe the commented out stuff we have on this 
        #   would solve this issue, so long as we are low, we keep adding 5 to the maxlen each frame
        #find other dancing/music software
        #   Very Nervous Sytem looks really really great
            #enhance magnitude calculation in terms of height, using the average juggling height as a good magnitude, as well
            #   'scaling' another way to say you are changing the measurement of how you do the magnitude and log scale would also change the 
            #   rep of the height, trying to scale height to magnitude
        #having issues with pygame notes not triggering in patterns, maybe because it thinks the same ball is peaking to soon
        #   and so it is not allowed to make the sound because it is too soon. sometimes sounds seem to bunch up as well, maybe this is a pygame issue.
        #move plots to new file
        #make simple tkinter gui
        #   wait on this
#could be dealt with dynamicly: contour_count_window, it needs to be a different length when the fps is 
#                                       high so that blurs dont get seen as new balls
#get the record feature to start working again
#   wait 5 seconds to start recording, use those 5 seconds to determine the fps and set it that way
#   try and record with increased fps in an empty project
#implement tempo detection(peaks per second), this could be hooked up via midi with virtualdj bpm
#   also check to see if pygame can change audio speed
#it may also be interesting to find an actual center of mass as well. This can also be done hemispherically if we 
#       can find out exactly which pixels are on/off.
#get rid of any library we are not using
#PLOTS:
#   try different window sizes for dif
#   plot average position, maybe true com and a com for either side of the screen
#   rebuild dif and corrcoef plots
#   make a corrcoef for the diffs



#known bugs:
#   crashes if there are too many random contours flashin in and out
#   tracking needs to be better on small throws

#column_sounds[random.getrandbits(1)].play() <-- gives a random 1 or 0
#todo


#predicting drops by detecting patterns that often come before them could be really interseting,
#   we could play around with showing a % likelihood that you are going to drop based on how stable the pattern is

#instead of just playing notes on peaks, notes could be played on the left/rights so they happen on throws



'''font                   = cv2.FONT_HERSHEY_SIMPLEX
    bottomLeftCornerOfText = (30,370)
    fontScale              = 6
    fontColor              = (0,125,255)
    lineType               = 4

    cv2.putText(frame,str(round(time.time()-start,1)), 
        bottomLeftCornerOfText, 
        font, 
        fontScale,
        fontColor,
        lineType)


            this is the stuff for handling a ball eclipsing another and resulting in 1 big contour
                    #missing_ball_count = average_contour_count - len(cx)
            #if missing_ball_count > 0:
            #    cx, cy = split_contours(cx, cy,average_contour_count,last_two_cx,last_two_cy,missing_ball_count)'''
