# import the necessary packages
from __future__ import print_function
import imutils
import colorsys
import math
from math import hypot
import time #for sending midi
import numpy as np #for webcam
from collections import deque # for tracking balls
import itertools
import collections
import imutils # for tracking balls
import pyautogui
from scipy import ndimage
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import datetime
from random import randint
import random
import scipy.stats as ss
from music_helper import get_notes_in_scale
from plot_helper import create_plots
from midi_helper import *
from video_helper import *
import video_helper
from settings import *
import settings
show_time = False
print_peaks = True
average_min_height = 30
max_balls = 3
can_lift = [True]*20
can_lift_master = True#not sure but this master may not be needed now that we have different 
                    #colored balls
max_balls = settings.max_balls
all_vx,all_vy,all_time_vx,all_time_vy,all_ay = [[] for _ in range(max_balls)],[[] for _ in range(max_balls)],[[] for _ in range(max_balls)],[[] for _ in range(max_balls)],[[] for _ in range(max_balls)]
last_peak_time,peak_count = [-.25]*20,0
midi_note_based_on_position_is_in_use,past_peak_heights,average_peak_height = False,deque(maxlen=6),-1 
average_catch_height = -1
def calculate_velocity(last_two_positions):
    return last_two_positions[0] - last_two_positions[1]
def calculate_time_velocity(velocity,time_since_previous_frame):
    return velocity / max(time_since_previous_frame,0.0001)
def calculate_acceleration(last_two_velocities):    
    return last_two_velocities[1] - last_two_velocities[0]
previous_frame_time = 0
temp_count = 0
def calculate_kinematics(frame_count):
    global previous_frame_time,temp_count
    time_since_previous_frame = time.clock() - previous_frame_time
    previous_frame_time = time.clock() 
    for i in range(len(all_cx)):
        if all_cx[i][-1] != 'X' and all_cx[i][-2] != 'X':
            last_two_cx = all_cx[i][-2:]
            last_two_cy = all_cy[i][-2:]
            if len(last_two_cx) > 1:
                all_vx[i].append(calculate_velocity(last_two_cx))
                all_vy[i].append(calculate_velocity(last_two_cy))
                #all_time_vx[i].append(calculate_time_velocity(all_vx[i][-1],time_since_previous_frame))
                #all_time_vy[i].append(calculate_time_velocity(all_vy[i][-1],time_since_previous_frame))            
                if len(all_vy[i]) > 2:
                    if all_vy[i][-1] != 'X' and all_vy[i][-2] != 'X':
                        all_ay[i].append(calculate_acceleration([all_vy[i][-2],all_vy[i][-1]]))
                else:
                    all_ay[i].append(0)
            else:
                all_vx[i].append(0)
                all_vy[i].append(0)
        else:
            all_vx[i].append('X')
            all_vy[i].append('X')
            #all_time_vx[i].append('X')
            #all_time_vy[i].append('X')    
            all_ay[i].append('X')
def determine_relative_positions():
    relative_positions = [[] for _ in range(max_balls)]
    last_cxs = []
    last_cxs_indices = []
    for i in range(len(settings.all_cx)):
        if all_cx[i][-1] != 'X':
            last_cxs.append(all_cx[i][-1])
    ranked_list_x = ss.rankdata(last_cxs)
    if len(last_cxs)>0:
        for i in range(0,len(last_cxs)):
            if ranked_list_x[i] == min(s for s in ranked_list_x):
                relative_positions[i]= 'left'
            elif ranked_list_x[i] == max(s for s in ranked_list_x):
                relative_positions[i]= 'right'
            else:
                relative_positions[i]= 'mid'
    return ['left', 'mid', 'right']
def ball_at_peak(vy_window):
    global peak_count
    number_of_frames_up = 4
    vy_window = vy_window[-(number_of_frames_up):] 
    if all(j > 0 for j in vy_window[-4:-1]) and vy_window[-1] <= 0 and abs(sum(vy_window[-4:-1])/3)>4:
        peak_count = peak_count+1
        print('ball at peak')
        return True
    else:
        return False
def peak_checker(index):
    global average_peak_height
    at_peak = False
    min_peak_period = .4
    current_all_vy = all_vy[index]
    if len(current_all_vy) > 2:
        if time.time()-last_peak_time[index] > min_peak_period:
            if ball_at_peak(current_all_vy) and time.time() - last_peak_time[index] > .5:
                last_peak_time[index] = time.time()
                current_all_cy = all_cy[index]
                past_peak_heights.append(current_all_cy[-1])
                average_peak_height = sum(past_peak_heights)/len(past_peak_heights)
                at_peak = True
    return at_peak
def catch_detected(index):
    number_of_frames_up = 4
    current_all_vy = all_vy[index]
    vy_window = current_all_vy[-(number_of_frames_up):]
    return (all(j < 0 for j in vy_window[-4:-1]) and vy_window[-1] >= 0)
def throw_detected(index):
    number_of_frames_up = 3
    #print(all_vy[index])
    current_all_vy = all_vy[index]
    #vy_window = collections.deque(itertools.islice(all_vy[index], 30-number_of_frames_up, 30)))
    vy_window = current_all_vy[-(number_of_frames_up):]
    if len(vy_window)>1:
        return (all(j > 0 for j in vy_window[-2:]) and vy_window[0] <= 0)
def determine_path_phase(index, frame_count):#look up webcam side warping
#push C to go into callibration mode, callibration starts after 5 seconds, a printout says
#   when it begins and when it completes. the info from callibration gets saved to a txt,
#   maybe the same txt that is used for the colors.
#when the program runs it gets its callibration info from the text file
    if len(all_ay[index]) > 0 and all_vy[index][-1]!='X':
        if path_phase[index] == 'throw' and all_vy[index][-1] > 0:
            settings.path_phase[index] = 'up'
        if path_phase[index] == 'catch':                
            settings.path_phase[index] = 'held'
        if all(isinstance(item, int) for item in all_ay[index][-3:]):
            recent_average_acceleration = sum(all_ay[index][-3:])/3
            if abs((-5)-recent_average_acceleration) < 4:#this 4 and the -5 are to be set with callibration
                #print('                        NOT IN HAND')
                if settings.in_hand[index] == True:
                    settings.path_phase[index] = 'throw'
                else:                
                    if all_vy[index][-1] > 0:
                        settings.path_phase[index] = 'up'
                    else:
                        if settings.path_phase[index] == 'up':
                            settings.path_phase[index] = 'peak'
                        elif settings.path_phase[index] == 'peak':
                            settings.path_phase[index] = 'down'
                settings.in_hand[index] = False
            else:            
                #print('                                             IN HAND')
                if settings.in_hand[index] == False:
                    settings.path_phase[index] = 'catch' 
                else:
                    settings.path_phase[index] = 'held'
                    if abs(all_ay[index][-1]) > 80 and settings.path_phase[index] != 'chop':
                        settings.path_phase[index] = 'chop'
                        print('CHOP!!')
                settings.in_hand[index] = True    
        else:
            settings.path_phase[index] = 'none'
    #print(path_phase[index]+ '       index: '+str(index))  
def determine_path_type(index,position):
    settings.path_type[index] = position
    if all_vx[index][-1] != 'X':
        if abs(all_vx[index][-1]) > average_min_height/5:
            settings.path_type[index] = settings.path_type[index] + ' cross'
        else:
            settings.path_type[index] = settings.path_type[index] + ' column'
        #if abs(xv) > average_min_height and abs(yv) < average_min_height:
            #path_type[index] = 'one'
    else:
        settings.path_type[index] = 'none'
def analyze_trajectory(index,relative_position, frame_count):
    if len(all_vx[index]) > 0:
        determine_path_phase(index, frame_count)
        determine_path_type(index,relative_position)
def write_colors_to_text_file():
    text_to_write = ''
    text_file = open("tracked_colors.txt", "w+")
    for c in video_helper.colors_to_track:
        for i in c:
            text_to_write = ','.join((str(i) for i in c))
        text_file.write(text_to_write+'\n')
        text_to_write = ''
    text_file.close() 
def set_color_to_track(frame,index):
    b,g,r = 0.0, 0.0, 0.0
    count = 0
    lowest_x = min(video_helper.color_selecter_pos[0],video_helper.color_selecter_pos[2])
    highest_x = max(video_helper.color_selecter_pos[0],video_helper.color_selecter_pos[2])
    lowest_y = min(video_helper.color_selecter_pos[1],video_helper.color_selecter_pos[3])
    highest_y = max(video_helper.color_selecter_pos[1],video_helper.color_selecter_pos[3])
    for i in range (lowest_x,highest_x):
        for k in range (lowest_y,highest_y):
            pixlb, pixlg, pixlr = frame[k,i]
            b += pixlb
            g += pixlg
            r += pixlr
            count += 1
    count = max(1,count)
    hsv_color = list(colorsys.rgb_to_hsv(((r/count)/255), ((g/count)/255), ((b/count)/255)))
    video_helper.colors_to_track[index] = hsv_color
    video_helper.most_recently_set_color_to_track = index
    #print(video_helper.colors_to_track[index][0]*255, video_helper.colors_to_track[index][1]*255, video_helper.colors_to_track[index][2]*255)
    print('write')
    write_colors_to_text_file()
    load_colors_to_track_from_txt()
def check_for_keyboard_input(camera,frame):
    key = cv2.waitKey(1) & 0xFF
    q_pressed = False
    if key == ord('q'):            
        q_pressed = True
    if key == ord('a'):
        cv2.destroyAllWindows()            
        video_helper.show_mask = not video_helper.show_mask
        video_helper.show_camera = not video_helper.show_camera
    if video_helper.show_camera:
        if key == ord('s'):       
            camera.set(cv2.CAP_PROP_SETTINGS,0.0) 
        if key == ord('z'):
            set_color_to_track(frame,0)
        if key == ord('x'):
            set_color_to_track(frame,1)
        if key == ord('c'):
            set_color_to_track(frame,2)
        if key == ord('n'):
            video_helper.colors_to_track[video_helper.most_recently_set_color_to_track][0] -= (1/255)
            write_colors_to_text_file()
        if key == ord('m'):
            video_helper.colors_to_track[video_helper.most_recently_set_color_to_track][0] += (1/255)
            write_colors_to_text_file()
    return q_pressed
def should_break(start,break_for_no_video,q_pressed):      
    what_to_return = False
    if time.time() - start > duration or break_for_no_video or q_pressed:
        what_to_return = True
    return what_to_return
def closing_operations(average_fps,vs,camera,out,all_mask):
    global midiout
    print("average fps: "+str(average_fps))
    print("peaks: "+str(peak_count))
    if using_midi:
        midiout = None
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
    global all_mask,all_vx,all_vy,all_ay
    camera = cv2.VideoCapture(0)
    soundscape_image = cv2.imread('soundscape.png',1)
    ret, previous_frame = camera.read()
    two_frames_ago = previous_frame
    vs, args, out = setup_camera()
    sounds, song = setup_audio()
    start,loop_count,num_high,previous_frame_time = time.time(),0,0,1.0
    at_peak, break_for_no_video = [-.25]*20,False
    contour_count_window, min_height_window,frame_count = deque(maxlen=3), deque(maxlen=60), 0
    while True:
        average_fps, grabbed, frame, loop_count, break_for_no_video = analyze_video(start,loop_count,vs,camera,args,frame_count)
        if loop_count>1 and frames_are_similar(frame, previous_frame):
            continue
        else:
            frame_count = frame_count+1
        old_frame,matched_indices_count = frame,0
        number_of_contours_seen, mask, original_mask, contour_count_window = update_contour_histories(frame,previous_frame,two_frames_ago,contour_count_window)
        if number_of_contours_seen > 0 and frame_count > 10:   
            calculate_kinematics(frame_count)             
            relative_positions = determine_relative_positions()
            for i in range(max_balls):
                if settings.all_cx[i][-1] != 'X':          
                    analyze_trajectory(i,relative_positions[i],frame_count)
                    cv2.imshow('ss',soundscape_image)
                    create_audio(i,soundscape_image)
        all_mask = show_and_record_video(frame,out,start,average_fps,mask,all_mask,original_mask,matched_indices_count,len(settings.scale_to_use))               
        two_frames_ago = previous_frame
        previous_frame = frame
        q_pressed = check_for_keyboard_input(camera,frame)
        if should_break(start,break_for_no_video,q_pressed):
            break
    end = closing_operations(average_fps,vs,camera,out,all_mask)
    ##create_plots(frame_count,start,end,frame_height)
run_camera()

