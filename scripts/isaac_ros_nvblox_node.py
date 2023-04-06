# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2022-2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
"""
Performance test for the Isaac ROS NvbloxNode.

In this test, messages loaded by DataLoaderNode are published in real-time
at the data loading stage. In the meantime, PlaybackNode records messages,
including TF messages generated by VisualSlamNode as a preprocessor, along
with their aqcuired timeline. In the main benchmark stage, PlaybackNode
publishes the recorded messages in real-time based on the timeline.
The graph consists of the following:
- Preprocessors:
    1. VisualSlamNode: performs VSLAM and publishes odom TF messages
- Graph under Test:
    1. NvbloxNode: performs 3D reconstruction

Required:
- Packages:
    - isaac_ros_visual_slam
    - isaac_ros_nvblox
- Datasets:
    - assets/datasets/r2b_dataset/r2b_hideaway
"""

from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode

from ros2_benchmark import BasicPerformanceCalculator, BenchmarkMode
from ros2_benchmark import MonitorPerformanceCalculatorsInfo
from ros2_benchmark import ROS2BenchmarkConfig, ROS2BenchmarkTest

ROSBAG_PATH = 'datasets/r2b_dataset/r2b_hideaway'

def launch_setup(container_prefix, container_sigterm_timeout):
    """Generate launch description for Isaac ROS NvbloxNode."""

    nvblox_node = ComposableNode(
        name='NvbloxNode',
        package='nvblox_ros',
        plugin='nvblox::NvbloxNode',
        namespace=TestIsaacROSNvbloxNode.generate_namespace(),
        parameters=[{'global_frame': 'odom',
                     'voxel_size': 0.10,
                     'slice_height': 0.75,
                     'min_height': 0.3,
                     'max_height': 1.0,
                     'esdf': True,
                     'esdf_2d': True,
                     'mesh': True,
                     'distance_slice': True,
                     'tsdf_integrator_max_integration_distance_m': 5.0,
                     'tsdf_integrator_truncation_distance_vox': 4.0,
                     'tsdf_integrator_max_weight': 20.0,
                     'esdf_integrator_min_weight': 2.0,
                     'esdf_integrator_max_distance_m': 2.0,
                     'esdf_integrator_min_site_distance_vox': 1.0,
                     'max_tsdf_update_hz': 0.0,
                     'max_color_update_hz': 5.0,
                     'max_mesh_update_hz': 0.0,
                     'max_esdf_update_hz': 0.0},
                    {'use_sim_time': False}],
        remappings=[('depth/image', 'depth'),
                    ('depth/camera_info', 'depth/camera_info'),
                    ('color/image', 'left/rgb'),
                    ('color/camera_info', 'left/camera_info')]
    )

    data_loader_node = ComposableNode(
        name='DataLoaderNode',
        namespace=TestIsaacROSNvbloxNode.generate_namespace(),
        package='ros2_benchmark',
        plugin='ros2_benchmark::DataLoaderNode',
        parameters=[{
            'publisher_period_ms': 1
        }],
        remappings=[
            ('d455_1_depth_image', 'data_loader/depth'),
            ('d455_1_depth_camera_info', 'data_loader/depth/camera_info'),
            ('d455_1_rgb_image', 'data_loader/left/rgb'),
            ('d455_1_rgb_camera_info', 'data_loader/left/camera_info')
            ]
    )

    visual_slam_node = ComposableNode(
        name='VisualSlamNode',
        namespace=TestIsaacROSNvbloxNode.generate_namespace(),
        package='isaac_ros_visual_slam',
        plugin='isaac_ros::visual_slam::VisualSlamNode',
        remappings=[('stereo_camera/left/image', 'hawk_0_left_rgb_image'),
                    ('stereo_camera/left/camera_info', 'hawk_0_left_rgb_camera_info'),
                    ('stereo_camera/right/image', 'hawk_0_right_rgb_image'),
                    ('stereo_camera/right/camera_info', 'hawk_0_right_rgb_camera_info'),
                    ('/tf', 'visual_slam/tf')],
        parameters=[{
                    'enable_rectified_pose': True,
                    'denoise_input_images': False,
                    'rectified_images': True,
                    }],
        extra_arguments=[
            {'use_intra_process_comms': False}])

    playback_node = ComposableNode(
        name='PlaybackNode',
        namespace=TestIsaacROSNvbloxNode.generate_namespace(),
        package='isaac_ros_benchmark',
        plugin='isaac_ros_benchmark::NitrosPlaybackNode',
        parameters=[{
            'data_formats': [
                'sensor_msgs/msg/Image',
                'sensor_msgs/msg/CameraInfo',
                'sensor_msgs/msg/Image',
                'sensor_msgs/msg/CameraInfo',
                'tf2_msgs/msg/TFMessage',
                ]
        }],
        remappings=[
            ('buffer/input0', 'data_loader/depth'),
            ('input0', 'depth'),
            ('buffer/input1', 'data_loader/depth/camera_info'),
            ('input1', 'depth/camera_info'),
            ('buffer/input2', 'data_loader/left/rgb'),
            ('input2', 'left/rgb'),
            ('buffer/input3', 'data_loader/left/camera_info'),
            ('input3', 'left/camera_info'),
            ('buffer/input4', 'visual_slam/tf'),
            ('input4', '/tf')],
    )

    monitor_node0 = ComposableNode(
        name='MonitorNode0',
        namespace=TestIsaacROSNvbloxNode.generate_namespace(),
        package='isaac_ros_benchmark',
        plugin='isaac_ros_benchmark::NitrosMonitorNode',
        parameters=[{
            'monitor_data_format': 'nvblox_msgs/msg/Mesh',
            'monitor_index': 0,
        }],
        remappings=[
            ('output', 'NvbloxNode/mesh')
        ],
    )

    monitor_node1 = ComposableNode(
        name='MonitorNode1',
        namespace=TestIsaacROSNvbloxNode.generate_namespace(),
        package='isaac_ros_benchmark',
        plugin='isaac_ros_benchmark::NitrosMonitorNode',
        parameters=[{
            'monitor_data_format': 'nvblox_msgs/msg/DistanceMapSlice',
            'monitor_index': 1,
        }],
        remappings=[
            ('output', 'NvbloxNode/map_slice')
        ],
    )

    composable_node_container = ComposableNodeContainer(
        name='container',
        namespace=TestIsaacROSNvbloxNode.generate_namespace(),
        package='rclcpp_components',
        executable='component_container_mt',
        prefix=container_prefix,
        sigterm_timeout=container_sigterm_timeout,
        composable_node_descriptions=[
            data_loader_node,
            visual_slam_node,
            playback_node,
            monitor_node0,
            monitor_node1,
            nvblox_node
        ],
        output='screen'
    )

    return [composable_node_container]

def generate_test_description():
    return TestIsaacROSNvbloxNode.generate_test_description_with_nsys(launch_setup)


class TestIsaacROSNvbloxNode(ROS2BenchmarkTest):
    """Performance test for the Isaac ROS NvbloxNode."""

    # Custom configurations
    config = ROS2BenchmarkConfig(
        benchmark_name='Isaac ROS NvbloxNode Benchmark',
        input_data_path=ROSBAG_PATH,
        benchmark_mode=BenchmarkMode.TIMELINE,
        # Enable trial buffering to get complete output from vslam preprocessor node
        enable_trial_buffer_preparation=True,
        # Ask DataLoaderNode to play messages in real-time
        load_data_in_real_time=True,
        # Ask PlaybackNode to re-record timeline for playing in the timeline mode
        record_data_timeline=True,
        # Publish /tf_static messages beforehand
        publish_tf_static_messages_in_set_data=True,
        # The number of frames to be buffered (0 means not restricted)
        playback_message_buffer_size=0,
        # The rosbag is about 5 seconds long, setting timeout accordingly
        start_recording_service_timeout_sec=20,
        start_recording_service_future_timeout_sec=25,
        start_monitoring_service_timeout_sec=30,
        play_messages_service_future_timeout_sec=25,
        default_service_future_timeout_sec=35,
        monitor_info_list=[
            MonitorPerformanceCalculatorsInfo(
                'start_monitoring0',
                [BasicPerformanceCalculator({'report_prefix': 'mesh'})]),
            MonitorPerformanceCalculatorsInfo(
                'start_monitoring1',
                [BasicPerformanceCalculator({'report_prefix': 'map_slice'})])
        ]
    )

    def test_benchmark(self):
        self.run_benchmark()
