"""
This is a helper class that handles the audio recording and sending it to SpeechAce
"""
# -*- coding: utf-8 -*-
# pylint: disable=import-error, wrong-import-order

import _thread as thread
import binascii
import json
import subprocess
import time
import wave
import math
import pyaudio
from six.moves import queue

import rospy
from r1d1_msgs.msg import AndroidAudio

class AudioRecorder:
    """
    Helper class that handles audio recording, converting to wav, and sending to SpeechAce
    """

    # CONSTANTS
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 48000

    CHUNK = 16000
    ANDROID_MIC_TO_ROS_TOPIC = 'android_audio'
    EXTERNAL_MIC_NAME = 'USB audio CODEC: Audio (hw:1,0)'

    USE_USB_MIC = True

    def __init__(self):
        # True if the phone is currently recording
        self.is_recording = False

        # Holds the audio data that turns into a wav file
        # Needed so that the data will be saved when recording audio in the new thread
        self.buffered_audio_data = []

        # 0 if never recorded before, odd if is recording, even if finished recording
        self.has_recorded = 0

        # Audio Subscriber node
        self.sub_audio = None

        # True if actually recorded from android audio
        # False so that it doesn't take the last audio data
        # Without this it won't send a pass because it didn't hear you message 
        self.valid_recording = True

        # placeholder variable so we can see how long we recorded for
        self.start_recording_time = 0
        
        if USE_USB_MIC: #start recording so we dont have to repoen a new stream every time
            thread.start_new_thread(self.start_audio_stream, ())


    def start_audio_stream(self):
        mic_index = None
        audio = pyaudio.PyAudio()
        info = audio.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')

        #print(numdevices)
        #print("# of devices")

        for i in range(0, numdevices):

            #print(audio.get_device_info_by_host_api_device_index(0, i).get('name'))
            if (audio.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                if audio.get_device_info_by_host_api_device_index(0, i).get('name') == self.EXTERNAL_MIC_NAME:
                    mic_index = i
                    break

        if mic_index == None:
            self.valid_recording = False
            print('NOT RECORDING, NO USB AUDIO DEVICE FOUND!')
            pass
        else:
            # start Recording
            self.valid_recording = True            
            print('USB Audio Device found, recording!')
            self.stream = audio.open(format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE, input=True, frames_per_buffer=self.CHUNK, input_device_index=mic_index)

            # while self.is_recording:
            #     data = stream.read(self.CHUNK)
            #     buffered_audio_data.append(data)
            print(self.RATE)
            print(self.CHUNK)

            #TODO: publish on ros topic for bagging?
            while(not self.is_recording): 
                data = self.stream.read(self.CHUNK, exception_on_overflow=False) #just read data off the stream so it doesnt overflow

    def record_usb_audio(self, audio_filename, record_length_ms):

            frames = []
            for i in range(math.ceil((self.RATE / self.CHUNK) * (record_length_ms / 1000))):                
                data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)

            # Stops the recording
            #stream.stop_stream()
            #stream.close()
            #audio.terminate()

            wav_file = wave.open('.wav', 'wb')
            wav_file.setnchannels(AudioRecorder.CHANNELS)
            wav_file.setsampwidth(2)
            wav_file.setframerate(AudioRecorder.RATE)
            wav_file.writeframes(b''.join(frames))
            wav_file.close()

            elapsed_time = time.time() - self.start_recording_time
            print("recorded speech for " + str(elapsed_time) + " seconds")
            print('RECORDING SUCCESSFUL, writing to wav')


    def start_recording(self, audio_filename, recording_length_ms):
        """
        Starts a new thread that records the microphone audio.
        """
        self.is_recording = True
        self.has_recorded += 1
        self.buffered_audio_data = []  # Resets audio data
        self.start_recording_time = time.time()

        if self.valid_recording:
                self.record_usb_audio(audio_filename, recording_length_ms)
        else: 
                time.sleep((recording_length_ms / 1000) + 2) #if configured to use USB Mic, but it doesn't exist, then just sleep
        

    def stop_recording(self):
        """
        ends the recording and makes the data into
        a wav file. Only saves out if we are recording from Tega
        """
        self.is_recording = False  # Ends the recording
        self.has_recorded += 1
        time.sleep(.1)  # Gives time to return the data