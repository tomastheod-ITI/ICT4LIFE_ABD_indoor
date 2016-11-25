import cv2
import numpy as np
from sklearn.preprocessing import normalize
from datetime import datetime, timedelta
from lxml import etree

import img_processing_kinect as my_img_proc

import visualization as vis

kinect_max_distance=0



def org_xml_data_timeIntervals(skeleton_data):

    #get all time data from the list
    content_time = map(lambda line: line[0,1].split(' ')[3] ,skeleton_data)

    #date time library

    init_t = datetime.strptime(content_time[0],'%H:%M:%S')
    end_t = datetime.strptime(content_time[len(content_time)-1],'%H:%M:%S')
    x = datetime.strptime('0:0:0','%H:%M:%S')
    tot_duration = (end_t-init_t)

    #decide the size of time slices
    size_slice= tot_duration/12
    hours, remainder = divmod(size_slice.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    my_time_slice = timedelta(hours=hours,minutes=minutes,seconds=seconds)

    print 'time slice selected: ' + str(my_time_slice)

    #initialize list
    time_slices = []
    time_slices_append = time_slices.append

    #get data in every timeslices
    while init_t < (end_t-my_time_slice):
        list_time_interval = []
        list_time_interval_append = list_time_interval.append
        #print init_t
        for t in xrange(len(content_time)):

            if datetime.strptime(content_time[t],'%H:%M:%S')>= init_t and datetime.strptime(content_time[t],'%H:%M:%S') < init_t + my_time_slice:
                list_time_interval_append(skeleton_data[t])

            if datetime.strptime(content_time[t],'%H:%M:%S') > init_t + my_time_slice:
                break
        #print len(list_time_interval)

        ##save time interval without distinction of part of the day
        time_slices_append(list_time_interval)

        init_t= init_t+my_time_slice


    return time_slices


def get_coordinate_points(time_slice):

    #get all the coordinate points of head joint
    list_points = []
    list_points_append = list_points.append

    #get x,y,z,id
    map(lambda line: list_points_append([line[1][0],line[1][1]]),time_slice)
    zs = map(lambda line: float(line[1][2]),time_slice)
    ids =map(lambda line: np.int64(line[0][2]),time_slice)

    #apply filter to cancel noise
    x_f,y_f =my_img_proc.median_filter(list_points)

    return x_f,y_f,zs,ids


def occupancy_histograms_in_time_interval(my_room, list_poly, time_slices):
    # #get number of patches
    slice_col = my_img_proc.get_slice_cols()
    slice_row = my_img_proc.get_slice_rows()
    slice_depth = my_img_proc.get_slice_depth()

    my_data_temp = []
    my_data_temp_append = my_data_temp.append

    for i in xrange(0,len(time_slices)):
        ## Checking the start time of every time slice
        if(len(time_slices[i])>1):
            print 'start time: %s' %time_slices[i][0][0][1].split(' ')[3]
        else:
            print 'no data in this time slice'


        ## counter for every id should be empty
        track_points_counter = np.zeros((slice_col*slice_row*slice_depth))

        ##get x,y,z of every traj point after smoothing process
        x_filtered,y_filtered,zs,ids = get_coordinate_points(time_slices[i])

        ## display traj on img
        #temp_img = copy.copy(my_room)
        #my_img_proc.display_trajectories(temp_img, list_poly, x_filtered, y_filtered)

        ## count the occurances of filtered point x,y in every patches
        for p in xrange(0,len(list_poly)):

            for ci in xrange(0,len(x_filtered)):
                ## 2d polygon
                if list_poly[p].contains_point((int(x_filtered[ci]),int(y_filtered[ci]))):
                    ## 3d cube close to the camera
                    if zs[ci] < (kinect_max_distance/2):

                        track_points_counter[p*2] = track_points_counter[p*2] + 1
                        continue
                    else: ## 3d cube far from the camera

                        track_points_counter[(p*2)+1] = track_points_counter[(p*2)+1] + 1
                        continue


        ## save the data of every group in the final matrix
        my_data_temp_append(track_points_counter)

    ## normalize the final matrix
    normalized_finalMatrix = np.array(normalize(np.array(my_data_temp),norm='l2'))
    print 'final matrix size:'
    print normalized_finalMatrix.shape

    return normalized_finalMatrix


def histograms_of_oriented_trajectories(list_poly,time_slices):

    hot_all_data_matrix = []
    hot_all_data_matrix_append = hot_all_data_matrix.append

    for i in xrange(0,len(time_slices)):
        ##Checking the start time of every time slice
        # if(len(time_slices[i])>1):
        #     print 'start time: %s' %str(time_slices[i][0].split(' ')[8])
        # else:
        #     print 'no data in this time slice'

        #get x,y,z of every traj point after smoothing process
        x_filtered,y_filtered,zs,ids = get_coordinate_points(time_slices[i])

        #initialize histogram of oriented tracklets
        hot_matrix = []

        for p in xrange(0,len(list_poly)):
            tracklet_in_cube_f = []
            tracklet_in_cube_c = []
            tracklet_in_cube_append_f = tracklet_in_cube_f.append
            tracklet_in_cube_append_c = tracklet_in_cube_c.append

            for ci in xrange(0,len(x_filtered)):
                #2d polygon
                if list_poly[p].contains_point((int(x_filtered[ci]),int(y_filtered[ci]))):
                    ## 3d cube close to the camera
                    if zs[ci] < (kinect_max_distance/2):

                        tracklet_in_cube_append_c([x_filtered[ci],y_filtered[ci],ids[ci]])

                    else: ##3d cube far from the camera

                        tracklet_in_cube_append_f([x_filtered[ci],y_filtered[ci],ids[ci]])


            for three_d_poly in [tracklet_in_cube_c,tracklet_in_cube_f]:
                if len(three_d_poly)>0:

                    ## for tracklet in cuboids compute HOT following paper
                    hot_single_poly = my_img_proc.histogram_oriented_tracklets(three_d_poly)

                    ## compute hot+curvature
                    #hot_single_poly = my_img_proc.histogram_oriented_tracklets_plus_curvature(three_d_poly)

                else:
                    hot_single_poly = np.zeros((24))
                ##add to general matrix
                if len(hot_matrix)>0:
                    hot_matrix = np.hstack((hot_matrix,hot_single_poly))
                else:
                    hot_matrix = hot_single_poly


        hot_all_data_matrix_append(hot_matrix)


    ## normalize the final matrix
    normalized_finalMatrix = np.array(normalize(np.array(hot_all_data_matrix),norm='l2'))
    #print np.array(hot_all_data_matrix).shape

    return normalized_finalMatrix


def measure_joints_accuracy(skeleton_data):

    frame_step = 1

    mean_displcement_list = np.zeros((len(skeleton_data[0])-1,1))

    joint_distances = []
    joint_distances_append = joint_distances.append

    # for joint_id in xrange(1,len(skeleton_data[0])):
    #
    #     #euclidean distance between joint time[0] and joint time[framestep]
    #     eu_difference = map(lambda i: np.sqrt((int(float(skeleton_data[i+frame_step][joint_id,0]))- int(float(skeleton_data[i][joint_id,0])))**2 + \
    #         (int(float(skeleton_data[i+frame_step][joint_id,1])) - int(float(skeleton_data[i][joint_id,1])))**2) \
    #         if skeleton_data[i][joint_id,0] != 0. or skeleton_data[i+1][joint_id,0] != 0. else 0 \
    #            ,xrange(0,len(skeleton_data)-frame_step))
    #
    #     mean_displcement_list[joint_id-1] = np.sum(eu_difference)/len(eu_difference)
    #
    #     joint_distances_append(eu_difference)

    #print mean_displcement_list
##############
    #subject7_exit_entrance = [19676 ,16250,  1943]
    subject4_exit_entrance = [3867,6053,9053,11898,17584,25777]

    ##not optimized code but more understadable
    for joint_id in xrange(1,len(skeleton_data[0])):
        eu_difference = np.zeros((len(skeleton_data),1))
        for i in xrange(0,len(skeleton_data)-1):
            if skeleton_data[i][joint_id,0] == 0. or skeleton_data[i+1][joint_id,0] == 0.:
                continue
            if i in subject4_exit_entrance:
                continue
            #euclidean distance between joint time[0] and joint time[framestep]
            eu_difference[i] = np.sqrt((int(float(skeleton_data[i+1][joint_id,0]))- int(float(skeleton_data[i][joint_id,0])))**2 + \
            (int(float(skeleton_data[i+1][joint_id,1])) - int(float(skeleton_data[i][joint_id,1])))**2)
        joint_distances_append(eu_difference)
        mean_displcement_list[joint_id-1] = np.sum(eu_difference)/len(eu_difference)


    joint_distances_filtered = []
    joint_distances_filtered_append = joint_distances_filtered.append
    for joint_id in xrange(1,len(skeleton_data[0])):

        ##store x,y for 1 joint each time over all frames
        list_points = []
        list_points_append = list_points.append
        for i in xrange(0,len(skeleton_data)):
            #if skeleton_data[i][joint_id,0] == 0.:
                #continue
            #if i in subject7_exit_entrance:
                #continue
            list_points_append((int(float(skeleton_data[i][joint_id,0])),int(float(skeleton_data[i][joint_id,1]))))

        ##apply filter
        x_f,y_f =my_img_proc.median_filter(list_points)

        eu_difference_filtered = np.zeros((len(skeleton_data),1))
        for i in xrange(0,len(x_f)-1):

            #if x_f[i+1] == 0. or x_f[i] == 0.:
                #continue
            if i in subject4_exit_entrance:
                continue

            eu_difference_filtered[i] = np.sqrt((x_f[i+1]-x_f[i])**2 + (y_f[i+1]-y_f[i])**2)
        joint_distances_filtered_append(eu_difference_filtered)
    # print mean_displcement_list

###############

    ##get only the desired joint
    ##TODO: joints id is different with hetra
    my_joint_raw = map(lambda x: x,joint_distances[:1][0])
    my_joint_filtered=map(lambda x: x,joint_distances_filtered[:1][0])

    #difference between raw and filtered features
    diff = map(lambda pair: pair[0]-pair[1] , zip(my_joint_raw,my_joint_filtered))

    #get frames where joint displacement over threshold
    threshold = 15

    frames_where_joint_displacement_over_threshold = []
    map(lambda (i,d): frames_where_joint_displacement_over_threshold.append(i) if d>threshold else False , enumerate(diff))
    print len(frames_where_joint_displacement_over_threshold)


    ##display mean distance of every joints between frames
    #vis.plot_mean_joints_displacement(mean_displcement_list)

    ##display error each frame from selected joint
    vis.plot_single_joint_displacement_vs_filtered_points(my_joint_raw,my_joint_filtered)

    return frames_where_joint_displacement_over_threshold


def feature_extraction_video_traj(skeleton_data):

    ##divide image into patches(polygons) and get the positions of each one
    my_room = np.zeros((414,512),dtype=np.uint8)
    list_poly = my_img_proc.divide_image(my_room)


    ##--------------Pre-Processing----------------##

    ##reliability method
    measure_joints_accuracy(skeleton_data)

    skeleton_data_in_time_slices = org_xml_data_timeIntervals(skeleton_data)



    ##--------------Feature Extraction-------------##
    print 'feature extraction'

    ## count traj points in each region and create hist
    occupancy_histograms = occupancy_histograms_in_time_interval(my_room, list_poly, skeleton_data_in_time_slices)


    ## create Histograms of Oriented Tracks
    HOT_data = histograms_of_oriented_trajectories(list_poly,skeleton_data_in_time_slices)


    return [occupancy_histograms,HOT_data]

    #cluster_prediction = my_exp.main_experiments(HOT_data)
