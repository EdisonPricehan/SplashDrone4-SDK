import PySimpleGUI as sg

# constants and defaults
header_font = 'Helvitica'
header_font_size = 13

default_hori_speed = 1
default_vert_speed = 0.5


def updateWindowFlyReport(fly_report):
    window['-ROLL-'].update('{:0.1f}'.format(fly_report.ATTRoll))
    window['-PITCH-'].update('{:0.1f}'.format(fly_report.ATTPitch))
    window['-YAW-'].update("{:0.1f}".format(fly_report.ATTYaw))
    window['-LAT-'].update(fly_report.Lat)
    window['-LON-'].update(fly_report.Lon)
    window['-ALT-'].update("{:0.1f}".format(fly_report.Altitude))
    window['-GPS-HEAD-'].update("{:0.1f}".format(fly_report.GpsHead))
    window['-HS-'].update('{:0.2f}'.format(fly_report.FlySpeed))
    window['-VS-'].update('{:0.2f}'.format(fly_report.VSpeed))
    window['-THROTTLE-'].update(fly_report.InGas)
    window['-GPS-'].update(fly_report.GpsNum)
    window['-FLYTIME-'].update('{:d}'.format(fly_report.FlyTime_Sec))


def updateWindowBatteryReport(battery_report):
    window['-BAT_VOLT-'].update('{:0.1f}'.format(battery_report.Voltage))
    window['-BAT_REM_CAP-'].update('{:d}'.format(battery_report.RemainCap))
    window['-BAT_REM_PER-'].update('{:d}'.format(battery_report.Percent))
    window['-BAT_REM_TIME-'].update('{:d}'.format(battery_report.RemainHoverTime))
    window['-BAT_TEMP-'].update('{:d}'.format(battery_report.temperature))


def updateWindowGimbalReport(gimbal_report):
    window['-GIMBAL_ROLL-'].update('{:0.1f}'.format(gimbal_report.roll))
    window['-GIMBAL_PITCH-'].update('{:0.1f}'.format(gimbal_report.pitch))
    window['-GIMBAL_YAW-'].update('{:0.1f}'.format(gimbal_report.yaw))


def updateWindowGimbalControl(gimbal_control):
    window['-GIMBAL_SET_ROLL-'].update('{:d}'.format(gimbal_control.roll))
    window['-GIMBAL_SET_PITCH-'].update('{:d}'.format(gimbal_control.pitch))
    window['-GIMBAL_SET_YAW-'].update('{:d}'.format(gimbal_control.yaw))


fly_report_col = [
    [sg.Text('Flight Status', size=(30, 1), justification='center', font=(header_font, header_font_size))],
    [sg.Text('Roll (deg)', size=(15, 1)), sg.Text(size=(15, 1), key='-ROLL-')],
    [sg.Text('Pitch (deg)', size=(15, 1)), sg.Text(size=(15, 1), key='-PITCH-')],
    [sg.Text('Yaw (deg)', size=(15, 1)), sg.Text(size=(15, 1), key='-YAW-')],
    [sg.Text('Latitude', size=(15, 1)), sg.Text(size=(15, 1), key='-LAT-')],
    [sg.Text('Longitude', size=(15, 1)), sg.Text(size=(15, 1), key='-LON-')],
    [sg.Text('Altitude (m)', size=(15, 1)), sg.Text(size=(15, 1), key='-ALT-')],
    [sg.Text('GPS-HEAD', size=(15, 1)), sg.Text(size=(15, 1), key='-GPS-HEAD-')],
    [sg.Text('HSpeed (m/s)', size=(15, 1)), sg.Text(size=(15, 1), key='-HS-')],
    [sg.Text('VSpeed (m/s)', size=(15, 1)), sg.Text(size=(15, 1), key='-VS-')],
    [sg.Text('Throttle (0-100)', size=(15, 1)), sg.Text(size=(15, 1), key='-THROTTLE-')],
    [sg.Text('nGPS', size=(15, 1)), sg.Text(size=(15, 1), key='-GPS-')],
    [sg.Text('Fly Time (s)', size=(15, 1)), sg.Text(size=(15, 1), key='-FLYTIME-')]]

battery_report_col = [
    [sg.Text('Battery Status', size=(30, 1), justification='center', font=(header_font, header_font_size))],
    [sg.Text('Voltage (V)', size=(20, 1)), sg.Text(size=(15, 1), key='-BAT_VOLT-')],
    [sg.Text('Remaining Cap (mAh)', size=(20, 1)), sg.Text(size=(15, 1), key='-BAT_REM_CAP-')],
    [sg.Text('Remaining Percentage (%)', size=(20, 1)), sg.Text(size=(15, 1), key='-BAT_REM_PER-')],
    [sg.Text('Remaining Hover Time (min)', size=(20, 1)), sg.Text(size=(15, 1), key='-BAT_REM_TIME-')],
    [sg.Text('Temperature (Cel)', size=(20, 1)), sg.Text(size=(15, 1), key='-BAT_TEMP-')]]

gimbal_report_col = [
    [sg.Text('Gimbal Status', size=(30, 1), justification='center', font=(header_font, header_font_size))],
    [sg.Text('Roll (deg)', size=(20, 1)), sg.Text(size=(15, 1), key='-GIMBAL_ROLL-')],
    [sg.Text('Pitch (deg)', size=(20, 1)), sg.Text(size=(15, 1), key='-GIMBAL_PITCH-')],
    [sg.Text('Yaw (deg)', size=(20, 1)), sg.Text(size=(15, 1), key='-GIMBAL_YAW-')]]

plr_led_col = [[sg.Text("Payload Release & LED", justification='center', font=(header_font, header_font_size))],
               [sg.Checkbox('Payload Release 1', default=False, enable_events=True, key='-PLR1-'),
                sg.Checkbox('Payload Release 2', default=False, enable_events=True, key='-PLR2-'),
                sg.Checkbox('Strobe Light', default=True, enable_events=True, key='-STROBE_LED-'),
                sg.Checkbox('Arm Light', default=True, enable_events=True, key='-ARM_LED-')]]

takeoff_land_col = [[sg.Text("Takeoff & Land", justification='center', font=(header_font, header_font_size))],
                    [sg.Radio('Standby', 'RADIO-TAKEOFF-LAND', default=True, key='-STANDBY-'),
                     sg.Radio('Takeoff', 'RADIO-TAKEOFF-LAND', default=False, key='-TAKEOFF-'),
                     sg.InputText(default_text='0.4', size=(5, 1), key='-TAKEOFF_HEIGHT-'), sg.Text('m'),
                     sg.Radio('Land', 'RADIO-TAKEOFF-LAND', default=False, key='-LAND-'),
                     sg.Radio('RTH', 'RADIO-TAKEOFF-LAND', default=False, key='-RTH-')]]

image_col = [[sg.Text("Video Streaming", justification='center', font=(header_font, header_font_size))],
             [sg.Image(key='-IMAGE-')]]

move3d_col = [
    [sg.Text("Movement in 3D", size=(30, 1), justification='center', font=(header_font, header_font_size))],
    [sg.Text("H Speed (m/s)"), sg.InputText(default_text='{:0.1f}'.format(default_hori_speed), size=(5, 1), key='-HS_SET-'),
     sg.Text("V Speed (m/s)"),
     sg.InputText(default_text='{:0.1f}'.format(default_vert_speed), size=(5, 1), key='-VS_SET-')],
    [sg.Text("x (m)"), sg.InputText(default_text='0', size=(5, 1), key='-X-'),
     sg.Text("y (m)"), sg.InputText(default_text='0', size=(5, 1), key='-Y-'),
     sg.Text("z (m)"), sg.InputText(default_text='0', size=(5, 1), key='-Z-')],
    [sg.Listbox(values=[], size=(20, 5), key='-LIST_M3D-')],
    [sg.Button("Clear", enable_events=True, key='-CLEAR_M3D-'),
     sg.Button("Add", enable_events=True, key='-ADD_M3D-'),
     sg.Button("Execute", enable_events=True, key='-EXEC_M3D-'),
     sg.Button("Suspend (s)", enable_events=True, key='-SUSPEND_M3D-'),
     sg.InputText(default_text='10', size=(5, 1), key='-SUSPEND_TIME_M3D-'),
     sg.Button("Stop", enable_events=True, key='-STOP-M3D-')]]

waypoint_mission_col = [[sg.Text("Waypoint Mission Control", size=(30, 1), justification='center',
                                 font=(header_font, header_font_size))],
                        [sg.Text("Fly Speed (m/s)"), sg.InputText(default_text='6', size=(5, 1), key='-SPEED-'),
                         sg.Button("Set", key='-SPEED_SET-'),
                         sg.Text("Fly Altitude (m)"), sg.InputText(default_text='1', size=(5, 1), key='-ALT-'),
                         sg.Button("Set", key='-ALT_SET-')],
                        [sg.Text("Latitude"), sg.InputText(default_text='0', size=(10, 1), key='-LAT_WP-'),
                         sg.Text("Longitude"), sg.InputText(default_text='0', size=(10, 1), key='-LON_WP-'),
                         sg.Text("Hover time (s)"),
                         sg.InputText(default_text='5', size=(10, 1), key='-HOVER_TIME-')],
                        [sg.Listbox(values=[], size=(20, 5), key='-LIST_WP-')],
                        [sg.Button("Clear", enable_events=True, key='-CLEAR_WP-'),
                         sg.Button("Add", enable_events=True, key='-ADD_WP-'),
                         sg.Button("Execute", enable_events=True, key='-EXEC_WP-'),
                         sg.Button("Suspend (s)", enable_events=True, key='-SUSPEND_WP-'),
                         sg.InputText(default_text='10', size=(5, 1), key='-SUSPEND_TIME_WP-'),
                         sg.Button("Stop", enable_events=True, key='-STOP-WP-')]]

gimbal_control_col = [
    [sg.Text("Gimbal Control", size=(30, 1), justification='center', font=(header_font, header_font_size))],
    [sg.Text("Roll "),
     sg.Slider(range=(-45, 45), resolution=1, orientation='horizontal', default_value=0, enable_events=True,
               key='-GIMBAL_SET_ROLL-')],
    [sg.Text("Pitch "),
     sg.Slider(range=(-90, 90), resolution=1, orientation='horizontal', default_value=0, enable_events=True,
               key='-GIMBAL_SET_PITCH-')],
    [sg.Text("Yaw "),
     sg.Slider(range=(-45, 45), resolution=1, orientation='horizontal', default_value=0, enable_events=True,
               key='-GIMBAL_SET_YAW-')],
    [sg.Button("Reset", enable_events=True, key='-GIMBAL_RESET-')]]

camera_control_col = [[sg.Text("Camera Control", size=(30, 1), justification='center', font=(header_font, header_font_size))],
                      [sg.Button("Take Photo", enable_events=True, key='-PHOTO-'),
                       sg.Button("Record", enable_events=True, key='-RECORD-'),
                       sg.Button("Stop Recording", enable_events=True, key='-STOP_RECORD-')],
                      [sg.StatusBar("", size=(30, 1), key='-CAMERA_STATUS-')]]

# Overall layout
layout = [[sg.Column(fly_report_col, element_justification='c'), sg.VSeparator(),
           sg.Column(battery_report_col + gimbal_report_col, element_justification='c'), sg.VSeparator(),
           sg.Column(image_col, element_justification='c')],
          [sg.HSeparator()],
          [sg.Column(plr_led_col, element_justification='c'),
           sg.VSeparator(), sg.Column(takeoff_land_col, element_justification='c'),
           sg.VSeparator(), sg.Column(gimbal_control_col, element_justification='c'),
           sg.VSeparator(), sg.Column(camera_control_col, element_justification='c')],
          [sg.HSeparator()],
          [sg.Column(move3d_col, element_justification='c'),
           sg.VSeparator(), sg.Column(waypoint_mission_col, element_justification='c')]]

# Create the Window
window = sg.Window('SplashDrone 4 GUI', layout, auto_size_text=True, auto_size_buttons=True, finalize=True,
                   no_titlebar=False, resizable=True, location=(0, 0), grab_anywhere=True, scaling=1.5)
# window.Maximize()

# Send the slider value only when mouse left button release
window['-GIMBAL_SET_ROLL-'].bind('<ButtonRelease-1>', 'RELEASE')
window['-GIMBAL_SET_PITCH-'].bind('<ButtonRelease-1>', 'RELEASE')
window['-GIMBAL_SET_YAW-'].bind('<ButtonRelease-1>', 'RELEASE')
