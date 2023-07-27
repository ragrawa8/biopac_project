#!/usr/bin/env python
# encoding: utf-8
"""
multiconnect.py

Illustrates data streaming from AcqKnowledge to Python client code
using the multiple TCP connection mode.  This also illustrates using
variable sampling rates.

Copyright (c) 2009-2010 BIOPAC Systems, Inc. All rights reserved.
"""

# import standard Python modules

import sys
import os
import time

# import our biopacndt support module

import biopacndt
	
def main():	
	"""Execute the multiconnect sample applicaition.
	
	This loads a graph template that uses variable sampling rate
	and acquires 3 analog channels, 3 digital channels, and 2
	calculation channels.  The acquired data is printed to the
	screen as well as saved into files on disk with raw binary
	data.
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
	# our example graph template uses higher indexed analog and
	# digital channels that are not available for MP36.
	
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
	# 'var-sample-rate.gtl' within the "resources" subdirectory.
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
	
	# change data connection method to multiple.  This means that 
	# AcqKnowledge will open up an individual TCP connection per
	# channel to transfer the data.
	#
	# When in 'multiple' mode, we will need to construct one 
	# AcqNdtDataServer object for each channel being delivered.
	
	if acqServer.getDataConnectionMethod() != "multiple":
		acqServer.changeDataConnectionMethod("multiple")
		print "Data Connection Method Changed to: multiple"
	
	# instruct AcqKnowledge to send us data for all of the channels being
	# acquired and retain the array of enabled channel objects.
	
	enabledChannels = acqServer.DeliverAllEnabledChannels()
	
	# just for a test change the first channel delivery port to 50505.
	
	if len(enabledChannels) > 0:
		acqServer.ChangeDataConnectionPort(enabledChannels[0],50505)
	
	# construct our AcqNdtDataServer and channel recorder objects for each
	# channel.  Since we're in multiple mode, we need one per channel.
	
	dataServers = []
	dataRecorders = []
	for eCH in enabledChannels:
		# check which TCP port AcqKnowledge is using to send the data for
		# the channel
		
		chPort = acqServer.GetDataConnectionPort(eCH)
		
		# construct the data server to receive the data for this channel
		# from AcqKnowledge.  Note that the constructor takes a list of
		# channels, so we need to make a single-item list with the
		# channel object being received.
		
		channels = [eCH];
		dserver = biopacndt.AcqNdtDataServer(chPort, channels)
		
		# add the callback to print out the data for this channel to
		# the console.
		#
		# On Windows ActiveState Python exhibits dramatic inefficiencies
		# with using the print function, particularly in threaded
		# environments.  Using print for each sample is so inefficient
		# that even a full minute of additional processing time is not
		# enough to allow all the different threads to handle the
		# incoming data!
		#
		# For Windows, we will not print the data to the Python
		# console. Instead, we will just write it to disk.
		
		if os.name != 'nt':
			dserver.RegisterCallback("OutputToScreen",multiConnectToScreen)
		
		# create an AcqNdtChannelRecorder object to save the data of this
		# channel on disk.  This will create the binary output file within 
		# the "resources" directory.
		#
		# The AcqNdtChannelRecorder takes a full absolute path to the destination
		# file and the AcqNdtChannel object of the channel being recorded.
		
		filename = "multi-%s-%s.bin" % (eCH.Type, eCH.Index)
		fullpath = resourcePath + os.sep + filename
		recorder = biopacndt.AcqNdtChannelRecorder(fullpath, eCH)
		
		# add the callback for the channel recorder to the data server for
		# this channel to process the data as it is received and spool it
		# to disk
		
		dserver.RegisterCallback("BinaryWriter",recorder.Write)
		
		# track our allocated recorders for post-acquisition cleanup
		
		dataRecorders.append(recorder)
		
		# start the data server.  The data server will start listening for
		# AcqKnowledge to make the data connection for this channel and
		# start processing the channel's data.
		#
		# All AcqNdtDataServers must be started prior to initiating our
		# data acquisition.
		#
		# Note that each data server is running on its own independent
		# preemptive thread, so delivery and processing of the data
		# for each individual channel is not directly synchronized with
		# the ohters.  If sample-index multiple channel synchronization
		# is required, it will need to be implemented manually or,
		# alternatively, use the 'single' connection mode and break
		# apart each individual frame.
		
		dserver.Start()
		
		# track our allocated data servers for post-acquisition cleanup
		
		dataServers.append(dserver)
		
	# tell AcqKnowledge to begin acquiring data.
	
	acqServer.toggleAcquisition()

	# wait for AcqKnowledge to finish acquiring all of the data in the graph.
	
	acqServer.WaitForAcquisitionEnd()
		
	# give ourselves an additional 15 seconds to process any data that
	# may have been sent at the end of the acquisition or is waiting
	# in our data server queue.
		
	time.sleep(15)
	
	# stop all of the channel data servers now that all of the transmitted
	# information has been processed
	
	for ds in dataServers:
		ds.Stop()
		
	# stop the AcqNdtChannelRecorders.  This will flush the data for all of
	# the channels to disk and will close the files.
	
	for dr in dataRecorders:
		dr.Close()
		
def multiConnectToScreen(index, frame, enabledchannels):
	"""Callback for use with an AcqNdtDataServer to display incoming channel data in the console.
	
	index:	hardware sample index of the frame passed to the callback.
			to convert to channel samples, divide by the SampleDivider out
			of the channel structure.
	frame:	a tuple of doubles representing the amplitude of each channel
			at the hardware sample position in index.  The index of the
			amplitude in this tuple matches the index of the corresponding
			AcqNdtChannel structure in channelsInSlice.  Since we're using
			multiple mode, this should be a single element tuple.
	channelsInSlice:	a tuple of AcqNdtChannel objects indicating which
			channels were acquired in this frame of data.  The amplitude
			of the sample of the channel is at the corresponding location
			in the frame tuple.  Since we're using multiple mode, this should
			be a single element tuple.
	"""
	
	print "%s%s | %s | %s" % (enabledchannels[0].Type, enabledchannels[0].Index, index, frame)
	
if __name__ == '__main__':
	main()




