#!/usr/bin/env python
# encoding: utf-8

"""
singleconnection.py

Illustrates data streaming from AcqKnowledge to Python client code
using the single TCP connection mode.  This also illustrates using
variable sampling rates and how the AcqNdtDataServer class delivers
variable sampling rate data through its varying frames.

Note that in this example, all of the channels are downsampled, so
the actual hardware frame count is skipped on every odd hardware sample
index.

Copyright (c) 2009-2010 BIOPAC Systems, Inc. All rights reserved.
"""

# import standard Python modules

import sys
import os
import struct
import time

# import our biopacndt support module

import biopacndt

def main():     
        """Execute the singleconnection sample applicaition.
        
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
        #         print "MP150 not connected"
        #         return
        
        # Check if there is a data acquisition that is already running.
        # In order to acquire data into a new template, we need to halt
        # any previously running acquisition first.
        
        if acqServer.getAcquisitionInProgress():
                acqServer.toggleAcquisition()
                print "Current data acquistion stopped"
        
        # Send a template to AcqKnowledge.  We will send the template file
        # 'var-sample-no-base-rate.gtl' within the "resources" subdirectory.
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
        
        # instruct AcqKnowledge to send us data for all of the channels being
        # acquired and retain the array of enabled channel objects.
        
        enabledChannels = acqServer.DeliverAllEnabledChannels()
        
        # ask AcqKnowledge which TCP port number will be used when it tries
        # to establish its data connection
        
        singleConnectPort = acqServer.getSingleConnectionModePort()
        
        # set up an AcqNdtChannelRecorder object to save the data of our
        # first analog channel  on disk.  This will create the binary output
        # file within the "resources" directory.
        #
        # The AcqNdtChannelRecorder takes a full absolute path to the destination
        # file and the AcqNdtChannel object of the channel being recorded.
        
        channelToRecord = enabledChannels[0]
        filename = "%s-%s.bin" % (channelToRecord.Type, channelToRecord.Index)
        fullpath = resourcePath + os.sep + filename
        recorder = biopacndt.AcqNdtChannelRecorder(fullpath,channelToRecord)
        
        # construct our AcqNdtDataServer object which receives data from
        # AcqKnowledge.  Since we're using 'single' connection mode, we only
        # need one AcqNdtDataServer object which will handle all of our channels.
        #
        # The constructor takes the TCP port for the data connection and a list
        # of AcqNdtChannel objects correpsonding to the channels whose data is
        # being sent from AcqKnowledge.
        #
        # We got our TCP port above in the singleConnectionPort variable.
        #
        # The DeliverAllEnabledChannels() function returns a list of AcqNdtChannel
        # objects that ar enabled for acquisition, so we will pass in that
        # list from above.
        
        dataServer = biopacndt.AcqNdtDataServer(singleConnectPort, enabledChannels )
        
        # add our callback functions to the AcqNdtDataServer to process
        # channel data as it is being received.
        #
        # We will register the "outputtoScreen" function, defined in this file,
        # which will print out the data to the console as it comes in.
        #
        dataServer.RegisterCallback("OutputToScreen",outputToScreen)
        
        # The AcqNdtChannelRecorder has a "Write" callback that we will
        # also register to record the channel data to the file on disk.
        dataServer.RegisterCallback("BinaryRecorder",recorder.Write)
        
        # start the data server.  The data server will start listening for
        # AcqKnowledge to make its data connection and, once data starts
        # coming in, invoking our callbacks to process it.
        #
        # The AcqNdtDataServer must be started prior to initiating our
        # data acquisition.
        
        dataServer.Start()
        
        # tell AcqKnowledge to begin acquiring data.
        
        acqServer.toggleAcquisition()

        # wait for AcqKnowledge to finish acquiring all of the data in the graph.
        
        acqServer.WaitForAcquisitionEnd()
        
        # give ourselves an additional 15 seconds to process any data that
        # may have been sent at the end of the acquisition or is waiting
        # in our data server queue.
        
        # the "print" function of "outputToScreen" routine to output incoming sample values to Python console
        # experience some level of inefficiencies on Windows limiting the maximum rate
        # at which Python can process the incoming data.
        # So we put extra time as necessity to finish processing output of  all the results
        # to Python console and if exceptions are encountered the sleep timeout will need to be increased.
        # Our tests show that 15 second Sleep Time is enough for 10 seconds acquisition
        # at 1000 s/sec for 8 channels with variable sample rates (see template file
        # resources/var-sample-no-base-rate.gtl)
        time.sleep(15)
        
        # stop the AcqNdtDataServer after all of our incoming data has been
        # processed.
        
        dataServer.Stop()
        
        # stop the AcqNdtChannelRecorder.  This will flush out any data to
        # the file on disk with our first analog channel's binary data and
        # close the file.
        
        recorder.Close()                

def outputToScreen(index, frame, channelsInSlice):
        """Callback for use with an AcqNdtDataServer to display incoming channel data in the console.
        
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
        
        # NOTE:  'index' is set to a hardware acquisition sample index.  In
        # our sample data file, our acquisition sampling rate is 1kHz.
        #
        # Our sample data file uses variable sampling rates, and every
        # channel is downsampled.  The highest channel sampling rate is
        # only 500 Hz.  Therefore, every odd-indexed hardware sample position
        # does not contain any data!
        #
        # If the frame would be empty at a particular hardware index, the
        # callback does get invoked.  As a result, we won't see any odd
        # values of 'index' in our callback.
        
        print "%s | %s" % (index, frame)
                
if __name__ == '__main__':
        main()




