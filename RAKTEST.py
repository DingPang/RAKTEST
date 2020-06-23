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
        outputFile= open(outputFileName, 'w', encoding= "utf-8")
    else:
        outputFile= open(outputFileName, 'x', encoding= "utf-8")
    
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
        self.switcher= {
            "R": -1, # Retry
            "K": 0, # Keep running
            "E": "exit", # Exit
        }


    def execute (self, outputFile, logFile, ser):
        try:
            print(f"正在跑'{self.AT}'")
            ser.timeout=self.delay
            i=1
            while i < self.times+1:
                response = []
                if self.AT:
                    ser.write(self.AT.encode() + b'\r')
                while True:
                    raw = ser.readline()
                    if raw == b'':
                        break
                    line = raw.decode()
                    response.append(line)
                responseStr= "".join(response)
                print(responseStr.strip())
                selfAnsShort= responseStr[0:len(self.answer)]
                if len(responseStr.strip())<1:
                    print(f"{self.AT}收到空白回复")
                    logFile.write(f"{self.AT} 第{str(i)}个:收到空白回复\r\n")
                    if 'Empty' in self.wrongStats:
                        self.wrongStats['Empty']+= 1
                    else: 
                        self.wrongStats['Empty']=1
                elif selfAnsShort==self.answer: # if the response is correct
                    self.successTimes+=1
                else: # if the respnse is wrong
                    op= self.switcher.get(self.ifWrong)
                    if op == "exit":
                        self.reportOnLogFile(logFile, i, responseStr, op)
                        self.calErrorStats(outputFile)
                        ser.close()
                        sys.exit()

                    else:
                        self.reportOnLogFile(logFile, i, responseStr, op) 
                        i += op
                i+=1
            self.calErrorStats(outputFile)
        except serial.serialutil.SerialException as error:
            sys.exit(error.strerror)
    

    def reportOnLogFile(self, logFile, i, responseStr, op):
        '''
        This function writes on the logfile if an error has been detected, and it also updates the statistics that would be used to produce the
        outputfile.
        '''
        if responseStr.startswith("ERROR: "):
            errorCode= int(responseStr.strip()[6:])
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
            logFile.write(f"{self.AT} 第{str(i)}个出错:\r\n     {responseStr}")
        else:
            logFile.write(f"{self.AT} 第{str(i)}个出错, 根据指令结束整个过程:\r\n     {responseStr}")


    

    def calErrorStats(self, outputFile):
        outputFile.write(f"{self.AT}: 运行{self.times}次； 成功{self.successTimes}次； 成功率为{100*self.successTimes/self.times}% \r\n")
        for key in self.wrongStats:
            if type(key)==int:
                outputFile.write(f"     ERROR {key}: 出现{self.wrongStats[key]}次； 占全部的{100*self.wrongStats[key]/self.times}%\r\n")
            else:
                if key == 'others':
                    outputFile.write(f"     其他错误：出现{self.wrongStats[key]}次； 占全部的{100*self.wrongStats[key]/self.times}%\r\n")
                else:
                    outputFile.write(f"     空白回复：出现{self.wrongStats[key]}次； 占全部的{100*self.wrongStats[key]/self.times}%\r\n")
        outputFile.write("\r\n")


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
            logFile.write(f"Loop '{self.id}'/第{self.id}个循环：\r\n")
            outputFile.write(f"Loop '{self.id}'/第{self.id}个循环：\r\n")
            for c in self.CMDList:
                c.execute(outputFile, logFile, ser)
            logFile.write('\r\n')


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        print()
        sys.exit(1)
