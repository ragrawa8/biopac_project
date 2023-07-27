#!/usr/bin/env python
# encoding: utf-8
"""
autothreshold.py

Example usage of the biopacndt API that illustrates basic processing of
data being acquired and using the XML-RPC calls to modify the voltage
on the analog output.

To use this example, connect an 1/8" connection cable between the 
Analog Output 0 of the MP150 UIM and the first analog input channel
of the UIM.

This will start a data acquisition and examine the input of the first
analog channel.  Once the Python client sees that the maximum value of
the analog input has jumped by 1 Volt over the previous maximum value,
the Python client will request that the acquisition will be stopped.

A threaded timer is used to flip the analog output voltage from zero
to 5 Volts approximately 10 seconds after the acquisition is started.

Copyright (c) 2009-2010 BIOPAC Systems, Inc. All rights reserved.
"""

# import standard Python libraries

import sys
import os
import math
import threading
import time

# import our biopacndt module

import biopacndt

def main():	
	"""Runs the autothreshold.py sample application, illustrating acquisition toggling and output voltage control.
	
	To use this example, connect the Analog Output (Analog Out 0 on MP150)
	to the first analog channel of input.
	
	This will start a data acquisition and examine the input of the first
	analog channel.  Once the Python client sees that the maximum value of
	the analog input has jumped by 10% over the previous maximum value,
	the Python client will request that the acquisition will be stopped.
	
	A threaded timer is used to flip the analog output voltage from zero
	to 5 Volts approximately 10 seconds after the acquisition is started.
	"""
	
	# First we must locate an AcqKnowledge server, a computer that is
	# running AcqKnowledge with the networking feature and that is set
	# to respond to autodiscovery requests.
	#
	# We will use the "quick connect" function which locates the
	# first available AcqKnowledge on the network and returns an
	# AcqNdtServer object for it.
	
	acqServer = biopacndt.AcqNdtQuickConnect()
	if not acqServer:
		print "No AcqKnowledge servers found!"
		sys.exit()
		
	# check what type of MP device is being used by AcqKnowledge.
	# our example graph template uses analog output voltages which
	# is only available on the MP150.
	
	# if acqServer.getMPUnitType() != 150:
	# 	print "MP150 not connected"
	# 	return
	
	# Check if there is a data acquisition that is already running.
	# In order to acquire data into a new template, we need to halt
	# any previously running acquisition first.
	
	if acqServer.getAcquisitionInProgress():
		acqServer.toggleAcquisition()
		print "Current data acquistion stopped"
	
	# Send a template to AcqKnowledge.  We will send the template file
	# 'autothreshold.gtl' within the "resources" subdirectory.
	#
	# First construct a full path to this file on disk.
	
	resourcePath = os.getcwd() + os.sep + "resources"
	templateName = resourcePath + os.sep + "basic-rhy-resp-sample.gtl"
	
	# Send the template to AcqKnowledge.  We will use the LoadTemplate()
	# member of the AcqNdtServer class.  This helper function will
	# read the file into local memory, encode it appropriately, and
	# transfer the data to AcqKnowledge.
	#
	# Note that capitalization is important!  The member function starts
	# with a capital "L".
	
	print "Loading template %s" % templateName
	
	acqServer.LoadTemplate(templateName)
	
	# change data connection to single.  We're only using one channel to input
	# so single connection is fine
	
	if acqServer.getDataConnectionMethod() != "single":
		acqServer.changeDataConnectionMethod("single")
		print "Data Connection Method Changed to: single"
	
	# instruct AcqKnowledge to send us data for all of the channels being
	# acquired and retain the array of enabled channel objects.
	
	enabledChannels = acqServer.DeliverAllEnabledChannels()
	
	# construct an "AutoThreshold" instance.  This class contains a callback
	# which will sample sample 3 seconds worth of data on the input channel
	# and keep it internally for locating the max value within the last
	# three seconds.
	#
	# since we will record three seconds, we will want to convert the
	# seconds into the number of channel samples that we will keep in our
	# internal queue.  To do this we will examine the hardware acquisition
	# sampling rate as reported from the current data acquisition settings
	# in AcqKnowledge and convert to channel samples by using the channel's
	# sampling rate divider.
	
	channelToMonitor = enabledChannels[0]
	queueSize =  (acqServer.getSamplingRate()/channelToMonitor.SamplingDivider) * 3	# note that getSamplingRate() returns the acquisition rate in Hz, that is, samples per second.
	autoThreshold = AutoThreshold(channelToMonitor, queueSize, acqServer)
	
	# construct our AcqNdtDataServer object which receives data from
	# AcqKnowledge.  Since we're using 'single' connection mode, we only
	# need one AcqNdtDataServer object which will handle all of our channels.
	#
	# The constructor takes the TCP port for the data connection and a list
	# of AcqNdtChannel objects correpsonding to the channels whose data is
	# being sent from AcqKnowledge.
	
	singleConnectPort = acqServer.getSingleConnectionModePort()
	dataServer = biopacndt.AcqNdtDataServer(singleConnectPort, enabledChannels)
	
	# register the callback within our "AutoThreshold" object to process
	# incoming data.
	
	dataServer.RegisterCallback("AutoThreshold",autoThreshold.dataHandler)
	
	# start the data server.  The data server will start listening for
	# AcqKnowledge to make its data connection and, once data starts
	# coming in, invoking our callbacks to process it.
	#
	# The AcqNdtDataServer must be started prior to initiating our
	# data acquisition.
	
	dataServer.Start()
	
	# set the analog output voltage to zero volts.
	
	print "Setting analog output 0 to 0 Volts..."
	
	analogOutputChan = { "type":"analog", "index":0 }
	acqServer.setOutputChannel(analogOutputChan, 0.0)
	
	# construct a thread to flip our analog output voltage to 5V at a future
	# point in time
	
	raiseAnalogThread = ChangeAnalogOutputThread(acqServer, analogOutputChan)
	raiseAnalogThread.start()
	
	# tell AcqKnowledge to begin acquiring data.
	
	acqServer.toggleAcquisition()
	
	# wait for the acquisition to end
	
	acqServer.WaitForAcquisitionEnd()
	
	# stop the data collector as we no longer have data to process
	
	dataServer.Stop()

class ChangeAnalogOutputThread(threading.Thread):
	"""Basic helper class that flips the analog output to 5 Volts after waiting 10 seconds.
	"""
	
	def __init__(self, acqServer, analogOutputChan, **kwds):
		"""Construct a new thread to toggle the specifed analog output to 5V after a delay.
		
		acqServer:	AcqNdtServer object for use in communication
		analogOutputChan:	analog output channel structure whose voltage should be toggld
		kwds:	additional parameters for Threading library
		"""
		
		threading.Thread.__init__(self, **kwds)
		
		# store references to our server and output channel in internal properties
		
		self.__acqServer = acqServer
		self.__analogOutputChan = analogOutputChan
		
	
	def run(self):
		# first we will sleep and block for 10 seconds
		
		time.sleep(10)
		
		print "Flipping output voltage to 5 Volts..."
		
		# now flip the analog output to 5V.
		
		self.__acqServer.setOutputChannel(self.__analogOutputChan, 5.0)
		
class AutoThreshold:
	"""Class for performing trackign analysis of an input channel voltage and halt acquisition when the voltage changes by more than 1V of the max within a fixed window size.
	"""
	
	def __init__(self, channel, size, acqserver):
		"""Default constructor.
		
		channel:	set to the AcqNdtChannel object of the channel whose voltages
					should be examined
		size:		size of the moving window, in channel samples, for computing
					the windowed maximum value
		acqserver:	AcqNdtServer object used to make additional control requests.
		"""
		
		self.__channel = channel
		self.__queueSize = size
		self.__acqServer = acqserver
		
		## holds our internal queue of the most recent samples of our channel
		self.__queue = []

		## holds the maximum value as computed in the previous window of data.
		## Will be initialized after the first data sample is encountered
		self.__oldMaxValue = 0
		
		## maximum voltage change allowed betewen consecutive maximums.
		## once this is exceeded, the acquisition will be halted.
		self.__maxThreshold = 1
		
		## Holds if we already requested data acquisition to be stopped
		self.__stopProcessing = False
		
	def dataHandler(self, index, frame, channelsInSlice):
		"""Callback function for the AcqNdtDataServer class to examine incoming data.
		
		This will compute the windowed max and, if the windowed max changed by
		our voltage, we will halt the acquisition.
		
		index:	hardware sample index of the frame passed to the callback.
				to convert to channel samples, divide by the SampleDivider out
				of the channel structure.
		frame:	a tuple of doubles representing the amplitude of each channel
				at the hardware sample position in index.  The index of the
				amplitude in this tuple matches the index of the corresponding
				AcqNdtChannel structure in channelsInSlice.
		channelsInSlice:	a tuple of AcqNdtChannel objects indicating which
				channels were acquired in this frame of data.  The amplitude
				of the sample of the channel is at the corresponding location
				in the frame tuple.
		"""
		
		# if we've already requested the data acquisition to stop, we do
		# not need to process any information.
		
		if self.__stopProcessing:
			return
		
		# locate the position in our frame tuple for our channel's information.
		# since we're using 'single' mode delivery, if there are multiple
		# channels enabled in the graph they will be delivered to our callback
		# in mixed frames
		
		frameIndex = 0
		for ch in channelsInSlice:
			if self.__channel.Type != ch.Type and self.__channel.Index != ch.Index:
				frameIndex += 1
			else:
				break

		# not in frame.  This may occur if the channel we are examining is
		# downsampled and does not have an amplitude present in the current
		# hardware sample position.
		
		if frameIndex == len(frame):
			return
		
		# check if we are placing our first sample into the windowed data queue.
		# if so, initialize the previously seen maximum value to our first
		# data sample
		
		if len(self.__queue) == 0:
			self.__oldMaxValue=frame[frameIndex]
			
		# if we have not yet filled up our data buffer with 3 seconds of data,
		# just append the new sample position onto our queue and recompute our
		# maximum
		
		if len(self.__queue) < self.__queueSize:
			self.__queue.append(frame[frameIndex])
			
			if frame[frameIndex] > self.__oldMaxValue:
				self.__oldMaxValue=frame[frameIndex]
			
			return
		
		# if we get here, we do have three seconds of data alrady in our queue.
		# pop off the oldest sample and add our new sample
		
		self.__queue.pop(0)
		self.__queue.append(frame[frameIndex])
		
		# find the new maximum amplitude in our most recent three seconds of
		# data
		
		maxValue = self.__queue[0]
		for d in self.__queue:
			if d > maxValue:
				maxValue = d
		
		# compute the amplitude change between this maximum and 
		# the maximum of the previous window
		
		voltChange = maxValue-self.__oldMaxValue
		
		if voltChange > self.__maxThreshold and self.__acqServer.getAcquisitionInProgress():
			# if our voltage change between the most recent two
			# data windows has increased more than our target 1V, instruct the 
			# server to stop sending data.
			
			print "Data queue's max changed by more than 1 Volt from the previous max."
			print "Halting acquisition."
			self.__acqServer.toggleAcquisition()
			self.__stopProcessing = True
			return
		
		# retain the maximum value from the previous windowed set of data
		
		self.__oldMaxValue = maxValue	
	
if __name__ == '__main__':
	main()




