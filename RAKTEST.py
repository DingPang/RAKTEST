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
    Asking for input file and output file
    '''
    parser = argparse.ArgumentParser(description="RAK TEST")
    parser.add_argument('inputfile')
    parser.add_argument('outputfile')
    args = parser.parse_args()
    return [args.inputfile, args.outputfile]      

def main():
    IO= parse_args()
    inputFileName= IO[0]
    outputFileName= IO[1]
    logFileName= IO[1].split(".")[0]+"_Log"+".txt"
    inputFile= open(inputFileName)
    if path.exists(outputFileName):
        outputFile= open(outputFileName, 'w')
    else:
        outputFile= open(outputFileName, 'x')
    
    if path.exists(logFileName):
        logFile= open(logFileName, 'w')
    else:
        logFile= open(logFileName, 'x')
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
                    ser = serial.Serial(portInfo[0], portInfo[1], timeout=0)  #Might need to play around with the timeout argument:
                except serial.serialutil.SerialException as error:
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
        self.id= int (CMDNum)
        self.times= int(CMDInfo[0])
        self.AT= CMDInfo[1]
        self.delay= float(CMDInfo[2])
        self.ifWrong= CMDInfo[3]
        self.answer= " ".join(CMDInfo[4:]).strip()
        self.successTimes= 0
        self.wrongStats={}


    def execute (self, outputFile, logFile, ser):
        try:
            print(f"正在跑'{self.AT}'")
            ser.timeout=self.delay
            i=0
            while i < self.times:
                response = []
                if self.AT:
                    ser.write(self.AT.encode() + b'\r')
                while True:
                    raw = ser.readline()
                    if raw == b'':
                        break
                    line = raw.decode()
                    response.append(line)
                #time.sleep(self.delay)
                responseStr= "".join(response)#might need to play around
                print(responseStr)
                selfAnsShort= responseStr[0:len(self.answer)]
                if len(responseStr.strip())<1:
                    i-=1
                    self.times+=1
                elif selfAnsShort==self.answer: #????????????????
                    self.successTimes+=1
                else:
                    logFile.write(f"{str(i)}. {self.AT}出错: {responseStr}")
                    if responseStr.startswith("ERROR: "):
                        errorCode= int(responseStr[6:9].strip())# need to fix
                        if  errorCode in self.wrongStats:
                            self.wrongStats[errorCode]+= 1
                        else: 
                            self.wrongStats[errorCode]=1
                    else:
                        if 'others' in self.wrongStats:
                            self.wrongStats[responseStr[6:]]+= 1
                        else: 
                            self.wrongStats['others']=1
                i+=1
            self.calErrorStats(outputFile)
        except serial.serialutil.SerialException as error:
            sys.exit(error.strerror)
    
    def calErrorStats(self, outputFile):
        outputFile.write(f"{self.AT}: 运行{self.times}次； 成功{self.successTimes}次； 成功率为{100*self.successTimes/self.times}% \n")
        print(self.wrongStats)
        for key in self.wrongStats:
            if type(key)==int:
                outputFile.write(f"     ERROR {key}: 出现{self.wrongStats[key]}次； 占总错误的{100*self.wrongStats[key]/(self.times-self.successTimes)}%； 占全部的{100*self.wrongStats[key]/self.times}%")
            else:
                outputFile.write(f"     其他错误：出现{self.wrongStats[key]}次；占总错误的{100*self.wrongStats[key]/(self.times-self.successTimes)}%；占全部的{100*self.wrongStats[key]/self.times}%")
        outputFile.write("\n")

class loop:
    def __init__(self, loopNum, times):
        self.id= loopNum
        self.times= times
        self.CMDList= []
    

    def addCMD(self,CMDNum,CMDInfo):
        target= CMD(CMDNum,CMDInfo)
        self.CMDList.append(target)


    def play(self, ser, outputFile,logFile):
        for t in range(1,self.times+1):
            logFile.write(f"Loop '{self.id}'/第{self.id}个循环：\n")
            outputFile.write(f"Loop '{self.id}'/第{self.id}个循环：\n")
            for c in self.CMDList:
                c.execute(outputFile, logFile, ser)
                logFile.write('\r\n')
            logFile.write('\r\n')


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        print()
        sys.exit(1)
