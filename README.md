# SplashDrone4-ros1
The ROS1 package for the SplashDrone4, a drone developed by [Swellpro](https://www.swellpro.com/). 
This package allows you to control the drone and access its telemetry data.
Code are supposed to be run on Ubuntu 20.04 with ROS Noetic.


## System Dependencies (if you have not installed them yet)
We only need the C-version of [ZeroMQ](https://zeromq.org/download/):
```bash
sudo apt-get install libzmq3-dev
```

## Python Dependencies
It is advisable to use the system python (by default 3.8.10 on Ubuntu 20.04) and install the required packages of this repo using system's pip.
Using miniconda (or other virtual environments) might cause dependency conflicts issues.

First make sure python3 is used as the default python version:
```bash
sudo apt install python-is-python3
```
Then install the required python packages:
```bash
pip install utm, pyuput 
```
Since PySimpleGUI is not maintained on PyPI, you need to install it from the source:
```shell
pip install --upgrade --extra-index-url https://PySimpleGUI.net/install PySimpleGUI
```

## Building the ROS package
In a newly opened terminal, make sure ros1's base workspace is sourced:
```bash
source /opt/ros/noetic/setup.bash
```
or
```bash
source /opt/ros/noetic/setup.zsh
```
if you are using zsh.

Create a new ROS workspace if you haven't done so:
```bash
mkdir -p ~/splashdrone_ws/src
```
Then, clone the SplashDrone4-ros package into the `src` directory:
```bash
git clone git@github.com:EdisonPricehan/SplashDrone4-ros.git
```
Then checkout the ros1 branch:
```bash
git checkout ros1
```
Then, navigate to the root of your ROS workspace (e.g., `~/splashdrone_ws`):
```bash
catkin_make
```
This will build the package and create the necessary files in the `devel` directory.
If you run into cmake error like
```
Compatibility with CMake < 3.5 has been removed from CMake.
```
you can instruct CMake to override the compatibility check by setting the `CMAKE_POLICY_VERSION_MINIMUM` environment variable:
```bash
export CMAKE_POLICY_VERSION_MINIMUM=3.5
```
then run `catkin_make` again.


## Running the ROS package
Make sure the ROS workspace is sourced:
```bash
source ~/splashdrone_ws/devel/setup.bash
```
or
```bash
source ~/splashdrone_ws/devel/setup.zsh
```
if you are using zsh.

Then, you can run the ROS launch file to start the SplashDrone4 node and the GUI:
```bash 
roslaunch splashdrone start_all.launch
```
This will start the SplashDrone4 node and the GUI. 
You can then control the drone and access its telemetry data through the GUI.

![img](images/splashdrone_gui.png)

