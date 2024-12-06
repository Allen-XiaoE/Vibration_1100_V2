import sys,time
import json
from window import Ui_MainWindow
from rws import RWS
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal

class UI(QMainWindow, Ui_MainWindow):

    def __init__(self):
        self.__get_config()
        super(UI, self).__init__()
        self.setupUi(self)
        self.rws = RWS(url=self.url)
        self.viration_test_button.clicked.connect(self.vibration_test)
        self.get_serial_number_button.clicked.connect(self.get_serial)
        self.stop_button.clicked.connect(self.stop)
        self.gotosyncpose_button.clicked.connect(self.gotosyncpos)
        self.motor_on_button.clicked.connect(self.motoron)
        self.vibration = Vibration(self.rws,self.dir)
        self.vibration.update_status.connect(self.update_status)
        self.vibration.error.connect(self.error)
        self.vibration.rapid_manual_start.connect(self.rapid_manual_start_vib)
        self.goto_syncpos = GotoSyncPos(self.rws,self.dir)
        self.goto_syncpos.update_status.connect(self.update_status)
        self.goto_syncpos.error.connect(self.error)
        self.goto_syncpos.rapid_manual_start.connect(self.rapid_manual_start_gosyncpos)

    def __get_config(self):
        with open('setting.json') as f:
            settings = json.load(f)
            env = settings['env']
            env = settings['envlist'][env]
            self.url = settings[env]['URL']
            self.dir = settings[env]['DIR']

    def update_status(self, message):
        self.status_text.append(message)

    def error(self,message):
        QMessageBox.warning(self, "Warning", message)
    
    def rapid_manual_start_vib(self,message):
        reply = QMessageBox.question(self,'Confirm',message,QMessageBox.Yes | QMessageBox.No,  
                                     QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.vibration.continue_thread(rapid_start=True)
        else:
            self.vibration.continue_thread(rapid_start=False)

    def rapid_manual_start_gosyncpos(self,message):
        reply = QMessageBox.question(self,'Confirm',message,QMessageBox.Yes | QMessageBox.No,  
                                     QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.goto_syncpos.continue_thread(rapid_start=True)
        else:
            self.goto_syncpos.continue_thread(rapid_start=False)

    def vibration_test(self):
        self.status_text.clear()
        if self.serial_number == '':
            QMessageBox.warning(self, "Warning", "机器人序列号不能为空!")
            return
        self.vibration.serial = self.serial_number.text()
        self.vibration.start()

    def stop(self):
        if self.rws.stopexcuseRapid() == 'OK':
            self.update_status('程序停止了！')
        else:
            QMessageBox.warning(self, "Warning", "程序停止时出现问题,请检查控制柜状态！")
            return

    def gotosyncpos(self):
        self.status_text.clear()
        if self.serial_number == '':
            QMessageBox.warning(self, "Warning", "机器人序列号不能为空!")
            return
        self.goto_syncpos.serial = self.serial_number.text()
        self.goto_syncpos.start()
        
    def motoron(self):
        if self.rws.motor("motoron") == 'OK':
            self.update_status("电机上电")
        else:
            QMessageBox.warning(self, "Warning", "电机上电失败,请检查控制柜状态！")
            return
    
    def get_serial(self):
        if self.rws.baseurl == "https://192.168.125.1":
            serial = self.rws.GETserial()
        else:
            serial = "1100-000001"
        self.serial_number.setText(serial)

class Vibration(QThread):

    error = pyqtSignal(str)
    update_status = pyqtSignal(str)
    rapid_manual_start = pyqtSignal(str)
    def __init__(self, rws,dir) -> None:
        super(Vibration, self).__init__()
        self.rws = rws
        self.serial = ''
        self.rapid_start = False
        self.dir = dir

    def run(self):

        if self.serial == "":
            self.error.emit(f"机器人序列号不能为空!")
            return
        
        if self.rws.connect_verification() != "OK":
            self.error.emit(f"控制柜连接失败,请检查控制柜状态!")
            return
        
        opmode = self.rws.GETopmode()
        if opmode != "AUTO":
            self.error.emit(f"当前控制柜状态为{opmode},请检查控制柜状态!")
            return
        
        if self.rws.motor("motoron") != "OK":
            self.error.emit("控制柜无法上电!")
            return
        else:
            self.update_status.emit('电机上电')
        
        module = f'{self.dir}//RAPID//IRB1100_Vibration_Test_v0.1.2_new_CFG_0528.modx'
        robot_type = self.rws.get_robot_type()
        if robot_type == "IRB 1100-4/0.58":
            module = f'{self.dir}//RAPID//IRB1100_Vibration_Test_580 with TSV autolog.modx'
            robot_name = 'IRB1100_0.58'
        elif robot_type == "IRB 1100-4/0.47":
            module = f'{self.dir}//RAPID//IRB1100_Vibration_Test_475 with TSV autolog.modx'
            robot_name = 'IRB1100_0.47'
        else:
            self.error.emit("机器人型号不是IRB1100 0.58M 或者 IRB1100 0.47M,请检查机器人型号!")
            return
        self.update_status.emit(f"机器人型号:{robot_name}")
        self.update_status.emit(f"机器人序列号:{self.serial}")

        _con = open(module, "r")
        content = _con.read()
        if self.rws.uploadfile("temp/vibration.modx", content=content) != "OK":
            self.error.emit("Rapid上传失败!")
            return

        if self.rws.loadmodule("temp/vibration.modx") != "OK":
            self.error.emit("Rapid载入失败!")
            return

        if self.rws.pptoRoutine("VibrationTest", "IRB1100_Vibration_Test") != "OK":
            self.error.emit("Rapid指针无法指到'VibrationTest'函数,请检查rapid内容中是否包括该函数!")
            return
        
        if self.rws.excuseRapid() != "OK":
            # self.error.emit("Rapid无法执行!")
            # return
            self.rapid_manual_start.emit("请在TPU上点击开始程序,完成请点Yes!")
            self.exec_()
            if not self.rapid_start:
                return
        
        # if self.rws.GETrapidstatus() == "stopped":
        #     self.rapid_manual_start.emit("请在TPU上点击开始程序,完成请点Yes!")
        #     self.exec_()
        #     if not self.rapid_start:
        #         return
        self.update_status.emit("程序VibrationTest运行开始")
           
        while self.rws.GETrapidstatus() != "stopped":
            time.sleep(2)
        self.update_status.emit("程序VibrationTest运行结束")
        file_number = robot_name + '_' + self.serial
        content = self.rws.getfile(path=f'HOME:/Auto_Log/1100_logs.log')
        self.rws.write_to_txt_file(content=content,file_path=f'{self.dir}//DATA//{file_number}.txt')

        if self.rws.unloadmodule("IRB1100_Vibration_Test") != "OK":
            self.error.emit("Rapid卸载失败!")

        if self.rws.deletefile("temp/vibration.modx") != "OK":
            self.error.emit("Rapid文件删除失败!")
        
        if self.rws.deletefile("HOME:/Auto_Log") != "OK":
            self.error.emit("信号记录文件删除失败!")
        self.update_status.emit("信号采集完成！")
        self.update_status.emit("测试结束！")
    
    def continue_thread(self,rapid_start):
        self.rapid_start = rapid_start
        self.quit()

class GotoSyncPos(QThread):

    error = pyqtSignal(str)
    update_status = pyqtSignal(str)
    rapid_manual_start = pyqtSignal(str)
    def __init__(self, rws, dir) -> None:
        super(GotoSyncPos, self).__init__()
        self.rws = rws
        self.dir = dir
        self.serial = ''
        self.rapid_start = False

    def run(self):

        if self.serial == "":
            self.error.emit(f"机器人序列号不能为空!")
            return
        
        if self.rws.connect_verification() != "OK":
            self.error.emit(f"控制柜连接失败,请检查控制柜状态!")
            return
        
        opmode = self.rws.GETopmode()
        if opmode != "AUTO":
            self.error.emit(f"当前控制柜状态为{opmode},请检查控制柜状态!")
            return
        
        if self.rws.motor("motoron") != "OK":
            self.error.emit("控制柜无法上电!")
            return
        else:
            self.update_status.emit('电机上电')
        
        module = f'{self.dir}//RAPID//IRB1100_Vibration_Test_v0.1.2_new_CFG_0528.modx'
        robot_type = self.rws.get_robot_type()
        if robot_type == "IRB 1100-4/0.58":
            module = f'{self.dir}//RAPID//IRB1100_Vibration_Test_580 with TSV autolog.modx'
            robot_name = 'IRB1100_0.58'
        elif robot_type == "IRB 1100-4/0.47":
            module = f'{self.dir}//RAPID//IRB1100_Vibration_Test_475 with TSV autolog.modx'
            robot_name = 'IRB1100_0.47'
        else:
            self.error.emit("机器人型号不是IRB1100 0.58M 或者 IRB1100 0.47M,请检查机器人型号!")
            return
        self.update_status.emit(f"机器人型号:{robot_name}")
        self.update_status.emit(f"机器人序列号:{self.serial}")

        _con = open(module, "r")
        content = _con.read()
        if self.rws.uploadfile("temp/vibration.modx", content=content) != "OK":
            self.error.emit("Rapid上传失败!")
            return

        if self.rws.loadmodule("temp/vibration.modx") != "OK":
            self.error.emit("Rapid载入失败!")
            return

        if self.rws.pptoRoutine("gotosyncpos", "IRB1100_Vibration_Test") != "OK":
            self.error.emit("Rapid指针无法指到'gotosyncpos'函数,请检查rapid内容中是否包括该函数!")
            return
        
        if self.rws.excuseRapid() != "OK":
            self.rapid_manual_start.emit("请在TPU上点击开始程序,完成请点Yes!")
            self.exec_()
            if not self.rapid_start:
                return
        
        # if self.rws.GETrapidstatus() == "stopped":
        #     self.rapid_manual_start.emit("请在TPU上点击开始程序,完成请点Yes!")
        #     self.exec_()
        #     if not self.rapid_start:
        #         return
        self.update_status.emit("程序gotosyncpos运行开始")
           
        while self.rws.GETrapidstatus() != "stopped":
            time.sleep(2)
        self.update_status.emit("程序gotosyncpos运行结束")

        if self.rws.unloadmodule("IRB1100_Vibration_Test") != "OK":
            self.error.emit("Rapid卸载失败!")

        if self.rws.deletefile("temp/vibration.modx") != "OK":
            self.error.emit("Rapid文件删除失败!")
        
        self.update_status.emit("机器人回到同步位！")
    
    def continue_thread(self,rapid_start):
        self.rapid_start = rapid_start
        self.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UI()
    window.show()
    sys.exit(app.exec_())