#!/usr/bin/env python

"""

"""
import os.path
from os import path
import argparse
import serial
import sys
import time

def parse_args():
    '''
    Asking for the input file and the output file
    '''
    parser = argparse.ArgumentParser(description="RAK TEST")
    parser.add_argument('inputfile')
    parser.add_argument('outputfile')
    args = parser.parse_args()
    return [args.inputfile, args.outputfile]      

def main():
    '''
    This main function gets executed first. 
    '''
    #IO stands for Input/Output
    IO= parse_args()
    inputFileName= IO[0]
    outputFileName= IO[1]
    logFileName= IO[1].split(".")[0]+"_Log"+".txt"
    inputFile= open(inputFileName)
    #Check if an file with the same name of Outputfile already exists
    if path.exists(outputFileName):
        outputFile= open(outputFileName, 'w', encoding= "utf-8")
    else:
        outputFile= open(outputFileName, 'x', encoding= "utf-8")
    #Check if an file with the same name of Logfile Outputfile already exists
    if path.exists(logFileName):
        logFile= open(logFileName, 'w', encoding= "utf-8")
    else:
        logFile= open(logFileName, 'x', encoding= "utf-8")
    lines= inputFile.readlines()
    loops=[]
    loopNum=0
    CMDNum=0
    portInfo= []
    ser=0
    for aline in lines:
        if lines.index(aline)==0:
            portInfo= aline.split(" ")
            if len(portInfo)<2:
                print("Port Info not complete")
                sys.exit(1)
            else:
                try:
                    #Setting ReadTimeOut to be zero just to initiate, we later give user the ability to change this time for every AT command:
                    ser = serial.Serial(portInfo[0], portInfo[1], timeout=0)  
                except serial.serialutil.SerialException as error:
                    print("Cannot Open This Serial Port/ Wrong Baudrate")
                    sys.exit(error.strerror)
        else:
            if aline.startswith("Loop"):
                loopNum+=1
                CMDNum=0
                loops.append(loop(loopNum, int(aline[4:])))
            elif aline.startswith("CMD"):
                CMDNum+=1
                CMDInfo= aline[3:].split(" ")
                loops[-1].addCMD(CMDNum,CMDInfo)
            elif  len(aline.strip()) == 0:
                pass
            else:
                print(f"You have entered a line (line {lines.index(aline)}) falsely in the {inputFileName}, please check.")
                sys.exit(1)
    for l in loops:
          l.play(ser, outputFile, logFile)
    ser.close()

class CMD:
    def __init__(self, CMDNum, CMDInfo):
        '''
        initiate an instance of CMD (a line in the input file.)
        '''
        self.id= int (CMDNum)
        self.times= int(CMDInfo[0])
        self.AT= CMDInfo[1]
        self.delay= float(CMDInfo[2])
        self.ifWrong= CMDInfo[3]
        self.answer= " ".join(CMDInfo[4:]).strip()
        self.successTimes= 0
        self.wrongStats={}
        self.switcher= {
            "R": -1, # Retry
            "K": 0, # Keep running
            "E": "exit", # Exit
        }


    def execute (self, outputFile, logFile, ser): 
        '''
        Using Pyserial to execute a line of AT command
        '''
        try:
            print(f"running'{self.AT}'")
            ser.timeout=self.delay
            i=1
            while i < self.times+1:
                if self.AT:
                    ser.write(self.AT.encode() + b'\r')
                responseStr=""
                while len(responseStr.strip())<1:
                    responseStr= self.read(ser)
                print(responseStr)
                selfAnsShort= responseStr[0:len(self.answer)]
                # if len(responseStr.strip())<1:
                #     print(f"{self.AT}received an empty response")
                #     logFile.write(f"{self.AT} No.{str(i)}: received an empty response\r\n")
                #     if 'Empty' in self.wrongStats:
                #         self.wrongStats['Empty']+= 1
                #     else: 
                #         self.wrongStats['Empty']=1
                if selfAnsShort.casefold()==self.answer.casefold(): # if the response is correct
                    self.successTimes+=1
                else: # if the respnse is wrong
                    op= self.switcher.get(self.ifWrong)
                    if op == "exit":
                        self.reportOnLogFile(logFile, i, responseStr, op)
                        self.calErrorStats(outputFile)
                        ser.close()
                        sys.exit()

                    else:
                        i += op
                        self.reportOnLogFile(logFile, i, responseStr, op) 
                        
                i+=1
            self.calErrorStats(outputFile)
        except (serial.serialutil.SerialException, KeyboardInterrupt) as error:
            sys.exit(error)
    

    def read (self, ser):
        '''
        This function is called to read from serial port
        '''
        response = []
        while True:
            raw = ser.readline()
            if raw == b'':
                break
            line = raw.decode()
            response.append(line.strip())
        responseStr= "".join(response)
        return responseStr


    def reportOnLogFile(self, logFile, i, responseStr, op):
        '''
        This function writes on the logfile if an error has been detected, and it also updates the statistics that would be used to produce the
        outputfile.
        '''
        if responseStr.startswith("ERROR: "):
            errorCode= responseStr.strip()
            if  errorCode in self.wrongStats:
                self.wrongStats[errorCode]+= 1
            else: 
                self.wrongStats[errorCode]=1
        else:
            if 'others' in self.wrongStats:
                self.wrongStats['others']+= 1
            else: 
                self.wrongStats['others']=1
        if not op == "exit":
            logFile.write(f"{self.AT} No.{str(i)}:\n     {responseStr}\n")
        else:
            logFile.write(f"{self.AT} No.{str(i)}, terminating the entire process:\n     {responseStr}\n")


    

    def calErrorStats(self, outputFile):
        '''
        This function simply calculate the errors and errors' rates, then write them to the ouput file.
        '''
        outputFile.write(f"{self.AT}: Total {self.times} runs; {self.successTimes} successes; success rate is {100*self.successTimes/self.times}%\n")
        for key in self.wrongStats:
            if key.startswith("ERROR"): 
                outputFile.write(f"     {key}: appeared {self.wrongStats[key]} times； error rate is {100*self.wrongStats[key]/self.times}%\n")
            else:
                if key == 'others':
                    outputFile.write(f"     Other errors: appeared {self.wrongStats[key]} times; rate is {100*self.wrongStats[key]/self.times}%\n")
                # else:
                #     outputFile.write(f"     Empty response: appeared {self.wrongStats[key]} times; rate is {100*self.wrongStats[key]/self.times}%\r\n")
        outputFile.write("\n")


class loop:
    def __init__(self, loopNum, times):
        '''
        initiate an instance of loop
        '''
        self.id= loopNum
        self.times= times
        self.CMDList= []
    

    def addCMD(self,CMDNum,CMDInfo):
        '''
        Adding a line of AT command to this loop
        '''
        target= CMD(CMDNum,CMDInfo)
        self.CMDList.append(target)


    def play(self, ser, outputFile,logFile):
        '''
        Runing/Playing this loop of AT Commands
        '''
        for t in range(1,self.times+1):
            logFile.write(f"Loop '{self.id}'\n")
            outputFile.write(f"Loop '{self.id}'\n")
            for c in self.CMDList:
                c.execute(outputFile, logFile, ser)
            logFile.write('\n')


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        print()
        sys.exit(1)
