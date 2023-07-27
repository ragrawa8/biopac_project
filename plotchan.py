#!/usr/bin/env python
# encoding: utf-8

"""
plotchan.py

Creates a plot on screen using a tkinter canvas to show calculation
channel data as it is streamed from AcqKnowledge.

This will create a window with a "Start Acquisition" button.  Once 
started, a timer will refresh the plotting area underneath the
button to plot the incoming data that has been received.

Copyright (c) 2010 BIOPAC Systems, Inc. All rights reserved.
"""

# import standard Python modules

import sys
import os
import struct
import time
from Tkinter import *

# import our biopacndt support module

import biopacndt

def main():     
        """Execute the plotchan sample applicaition.
        
        This loads a graph template that acquires a calculation channel
        computing a sine wave.  It constructs a canvas object and plots
        the incoming data in realtime.
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
        
        # Check if there is a data acquisition that is already running.
        # In order to acquire data into a new template, we need to halt
        # any previously running acquisition first.
        
        if acqServer.getAcquisitionInProgress():
                acqServer.toggleAcquisition()
                print "Current data acquistion stopped"
        
        # Send a template to AcqKnowledge.  We will send the template file
        # 'sinewave.gtl' within the "resources" subdirectory.
        #
        # First construct a full path to this file on disk.
        
        resourcePath = os.getcwd() + os.sep + "resources"
        templateName = resourcePath + os.sep + "sinewave.gtl"

        # Send the template to AcqKnowledge.  We will use the LoadTemplate()
        # member of the AcqNdtServer class.  This helper function will
        # read the file into local memory, encode it appropriately, and
        # transfer the data to AcqKnowledge.
        #
        # Note that capitalization is important!  The member function starts
        # with a capital "L".
        
        print "Loading template %s" % templateName

        acqServer.LoadTemplate(templateName)

        # change data connection method to single.  The single data connection
        # mode means that AcqKnowledge will make a single TCP network connection
        # to our client code to deliver the data, all channels being
        # delivered over that same connection.
        #
        # When in 'single' mode, we only need one AcqNdtDataServer object
        # which will process all channels.
        
        if acqServer.getDataConnectionMethod() != "single":
                acqServer.changeDataConnectionMethod("single")
                print "Data Connection Method Changed to: single"
        
        # enable the first calculation channel for delivery.
        
        calcChannels = acqServer.GetChannels('calc')
        acqServer.Deliver(calcChannels[0], True)
        
        enabledChannels = [ calcChannels[0] ]
        
        # ask AcqKnowledge which TCP port number will be used when it tries
        # to establish its data connection
        
        singleConnectPort = acqServer.getSingleConnectionModePort()
        
        # construct our AcqNdtDataServer object which receives data from
        # AcqKnowledge.  Since we're using 'single' connection mode, we only
        # need one AcqNdtDataServer object which will handle all of our data.
        #
        # The constructor takes the TCP port for the data connection and a list
        # of AcqNdtChannel objects correpsonding to the channels whose data is
        # being sent from AcqKnowledge.
        #
        # We got our TCP port above in the singleConnectionPort variable.
        
        dataServer = biopacndt.AcqNdtDataServer(singleConnectPort, enabledChannels)
        
        # create the PlotData object for showing our incoming data and
        # add its callback to the AcqNdtDataServer to update the plot
        
        plotData = PlotData(acqServer)
        dataServer.RegisterCallback("UpdatePlot", plotData.handleAcquiredData)
        
        # start the data server.  The data server will start listening for
        # AcqKnowledge to make its data connection and, once data starts
        # coming in, invoking our callbacks to process it.
        #
        # The AcqNdtDataServer must be started prior to initiating our
        # data acquisition.
        
        dataServer.Start()
        
        # enter the man GUI loop to display our window and wait for it
        # to be closed
        
        plotData.runMainWindowLoop()
        
        # stop the AcqNdtDataServer after all of our incoming data has been
        # processed.
        
        dataServer.Stop()
        
class PlotData:
	"""Class that creates a canvas object with tkinter and plots incoming network data.
	"""
	
	def __init__(self, server):
		"""Default constructor.  Creates and initializes our channel object.
		
		server:	an AcqNdtServer object to be used for the data acquisition.
		"""
		
		# store server instance in our attribute
		
		self.__server = server
		
		# get our Tk instance.
		
		self.__root = Tk()
		self.__root.title("plotchan.py")
		
		# create a button for starting our acquisition.  By using a button
		# to start the acquisition from within the Tkinter window, we avoid
		# any potential blocking that may occur during window creation and
		# display.
		
		self.__b = Button(self.__root, text='Start Acquisition')
		self.__b.pack(side=TOP)
		self.__b.config(command=self.startAcquisition)
		
		# create the canvas to use for drawing the data that has been
		# received
		
		self.__c = Canvas(self.__root, width=1000, height=300, bg='white')
		self.__c.pack()
		
		# trigger the canvas to update the plot every tenth of a second
		# to show any incoming data that has been received
		
		self.__c.after(100, self.updatePlot)
				
		# initialize our data point list of acquired sample amplitudes to
		# an empty list
		
		self.__chanData = []
	
	def runMainWindowLoop(self):
		""" Enters the main window loop to display data.
		"""
		
		self.__root.mainloop()
	
	def startAcquisition(self):
		"""Instructs AcqKnowledge to begin the data acquisition.
		"""
		
		# instruct AcqKnowledge to begin the acquisition
		
		self.__server.toggleAcquisition()
		
		# disable our button since we're a one-shot acquisition
		
		self.__b.config(state=DISABLED)
	
	def updatePlot(self):
		"""Redraw the canvas area of the window to reflect the latest data
		received from AcqKnowledge.
		"""		
		# erase the existing plot in the canvas
	
		self.__c.delete(ALL)
		
		if len(self.__chanData) > 2:
			# construct the coordinate list for our plot
			
			lineCoords = []
			for i in xrange(len(self.__chanData)):
				# first is x coordinate.  Our window is 1000 pixels wide and
				# we expect only 1000 samples to be acquired, so we'll use
				# one horizontal pixel per sample.
				
				lineCoords.append( i )
				
				# next is y coordinate.  We will put this at our canvas
				# center pixel minus the amplitude times half height.
				# We're expecting a sine wave, so the sample amplitudes
				# should range from [-1, 1].
				#
				# note that we use subtraction so positive amplitudes
				# go vertically upwards from center.
				
				lineCoords.append( 150 - ( self.__chanData[i] * 150 ) )
			
			# create the line for our canvas and plot the curve
			
			self.__c.create_line(lineCoords, fill='blue')
			
			# add an event when we were updated
			
			self.__server.insertGlobalEvent('screen refresh', 'defl', '')
		
		# reinstall our update timer to refresh the plot a tenth of
		# a second from now.  after() in tkinter is one-shot, so we
		# must always reinstall ourself to get called again.
		
		self.__c.after(100, self.updatePlot)

	def handleAcquiredData(self, index, frame, channelsInSlice):
		"""Callback for use with an AcqNdtDataServer to display incoming channel data in the canvas.
		
		index:  hardware sample index of the frame passed to the callback.
						to convert to channel samples, divide by the SampleDivider out
						of the channel structure.
		frame:  a tuple of doubles representing the amplitude of each channel
						at the hardware sample position in index.  The index of the
						amplitude in this tuple matches the index of the corresponding
						AcqNdtChannel structure in channelsInSlice
		channelsInSlice:        a tuple of AcqNdtChannel objects indicating which
						channels were acquired in this frame of data.  The amplitude
						of the sample of the channel is at the corresponding location
						in the frame tuple.
		"""
		
		# append the channel data to the end of our list of received data.
		
		self.__chanData.append(frame[0])
        
if __name__ == '__main__':
        main()




