#!/usr/bin/env python
# encoding: utf-8
"""
simplesample.py

This sample illustrates basic functionality of locating an AcqKnowledge
server, sending it a template to load over the network, and starting
to acquire data in the template.

Copyright (c) 2009-2010 BIOPAC Systems, Inc. All rights reserved.
"""

# import standard Python modules

import sys
import os
import time

# import our biopacndt support module

import biopacndt

def main():	
	""" Execute the simplesample.py example Python code.  
	
	This locates a server, sends it a template, and starts data acquisition 
	remotely.
	"""
	
	# First we must locate an AcqKnowledge server, a computer that is
	# running AcqKnowledge with the networking feature and that is set
	# to respond to autodiscovery requests.
	#
	# We will use the "quick connect" function which locates the
	# first available AcqKnowledge on the network and returns an
	# AcqNdtServer object for it.
	
	server = biopacndt.AcqNdtQuickConnect()
	if not server:
		print "No AcqKnowledge servers found!"
		sys.exit()
	
	# Check if there is a data acquisition that is already running.
	# In order to acquire data into a new template, we need to halt
	# any previously running acquisition first.
	
	if server.getAcquisitionInProgress():
		server.toggleAcquisition()
		print "Current data acquistion stopped"
		print
	
	# Send a template to AcqKnowledge.  We will send the template file
	# 'basic-acquisition.gtl' within the "resources" subdirectory.
	#
	# First construct a full path to this file on disk.
	
	templatePath = os.getcwd() + os.sep + "resources"
	templateName = templatePath + os.sep + "basic-rhy-resp-sample.gtl"
	
	# Send the template to AcqKnowledge.  We will use the LoadTemplate()
	# member of the AcqNdtServer class.  This helper function will
	# read the file into local memory, encode it appropriately, and
	# transfer the data to AcqKnowledge.
	#
	# Note that capitalization is important!  The member function starts
	# with a capital "L".
	
	print "Loading template %s" % templateName
	print
	
	server.LoadTemplate(templateName)
	
	# print out our first channel label
	
	print "First channel name:"
	print server.GetChannelLabel(server.GetAllChannels()[0]);
	print
	
	# Start data acquisition into our template.
	
	server.toggleAcquisition()
	
	# Wait a second and then check if we started the acquisition successfully.
	
	time.sleep(1)
	
	if server.getAcquisitionInProgress():
		print "Acquisiton started successfully. Check AcqKnowledge to ensure an acquisition is in progress."
	else:
		print "ERROR:  the acquisition did not start!"
		
if __name__ == '__main__':
	main()

