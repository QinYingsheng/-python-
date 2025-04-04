import pyaudio
import numpy as np
import math
import time
import sys
import csv
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
import tkinter as tk
from tkinter import ttk, messagebox
from threading import Thread
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class AdvancedSoundLevelMeter:
    def __init__(self):
        # 音频设置
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        self.reference_pressure = 2.0e-5
        
        # 数据记录设置
        self.record_interval = 0.5  # 秒
        self.max_records = 600
        self.records = deque(maxlen=self.max_records)
        self.timestamps = deque(maxlen=self.max_records)
        self.db_values = deque(maxlen=self.max_records)
        
        # 报警设置
        self.alarm_threshold = 85.0  # 默认报警阈值(dB)
        self.alarm_enabled = True
        self.alarm_triggered = False
        self.alarm_duration = 0
        
        # PyAudio
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.is_running = False
        
        # CSV文件
        self.csv_file = None
        self.csv_writer = None
        
        # 创建GUI
        self.root = tk.Tk()
        self.root.title("高级声级计 v1.0")
        self.setup_gui()
        
        # 图形初始化
        self.setup_plots()
        
    def setup_gui(self):
        """设置图形用户界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制", padding="10")
        control_frame.grid(row=0, column=0, sticky=tk.N)
        
        # 状态显示
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(control_frame, textvariable=self.status_var).grid(row=0, column=0, columnspan=2)
        
        # 当前dB值显示
        self.db_var = tk.StringVar(value="0.00 dB")
        ttk.Label(control_frame, textvariable=self.db_var, font=('Arial', 24)).grid(row=1, column=0, columnspan=2, pady=10)
        
        # 控制按钮
        ttk.Button(control_frame, text="开始", command=self.start).grid(row=2, column=0, sticky=tk.E, padx=5)
        ttk.Button(control_frame, text="停止", command=self.stop).grid(row=2, column=1, sticky=tk.W, padx=5)
        
        # 报警设置
        alarm_frame = ttk.LabelFrame(control_frame, text="报警设置", padding="10")
        alarm_frame.grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.EW)
        
        ttk.Label(alarm_frame, text="阈值(dB):").grid(row=0, column=0)
        self.threshold_entry = ttk.Entry(alarm_frame, width=8)
        self.threshold_entry.insert(0, str(self.alarm_threshold))
        self.threshold_entry.grid(row=0, column=1)
        
        self.alarm_check = ttk.Checkbutton(alarm_frame, text="启用报警", variable=tk.BooleanVar(value=self.alarm_enabled), 
                                          command=self.toggle_alarm)
        self.alarm_check.grid(row=1, column=0, columnspan=2)
        
        ttk.Button(alarm_frame, text="应用", command=self.update_threshold).grid(row=2, column=0, columnspan=2)
        
        # 报警状态指示器
        self.alarm_indicator = tk.Canvas(alarm_frame, width=20, height=20, bg='gray')
        self.alarm_indicator.grid(row=0, column=2, rowspan=3, padx=10)
        
        # 图形框架
        graph_frame = ttk.Frame(main_frame)
        graph_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 实时图形
        self.fig = plt.Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 配置网格权重
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # 窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def setup_plots(self):
        """设置图形"""
        self.ax = self.fig.add_subplot(111)
        self.line, = self.ax.plot([], [], 'b-')
        self.threshold_line = self.ax.axhline(y=self.alarm_threshold, color='r', linestyle='--', alpha=0.7)
        
        self.ax.set_xlim(0, self.max_records * self.record_interval)
        self.ax.set_ylim(30, 120)
        self.ax.set_xlabel('时间 (秒)')
        self.ax.set_ylabel('声级 (dB)')
        self.ax.set_title('实时声级监测')
        self.ax.grid(True)
        
    def toggle_alarm(self):
        """切换报警状态"""
        self.alarm_enabled = not self.alarm_enabled
        self.update_alarm_indicator()
        
    def update_threshold(self):
        """更新报警阈值"""
        try:
            new_threshold = float(self.threshold_entry.get())
            if 30 <= new_threshold <= 120:
                self.alarm_threshold = new_threshold
                self.threshold_line.set_ydata([self.alarm_threshold] * 2)
                self.canvas.draw()
                messagebox.showinfo("成功", f"报警阈值已更新为 {new_threshold} dB")
            else:
                messagebox.showerror("错误", "阈值必须在30-120 dB之间")
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            
    def update_alarm_indicator(self, triggered=False):
        """更新报警指示器"""
        color = 'red' if triggered else ('green' if self.alarm_enabled else 'gray')
        self.alarm_indicator.delete("all")
        self.alarm_indicator.create_oval(2, 2, 18, 18, fill=color, outline='black')
        
    def check_alarm(self, db):
        """检查是否触发报警"""
        if not self.alarm_enabled:
            return
            
        if db >= self.alarm_threshold:
            if not self.alarm_triggered:
                self.alarm_triggered = True
                self.alarm_duration = 0
                self.update_alarm_indicator(True)
                messagebox.showwarning("报警", f"声级超过阈值: {db:.2f} dB")
            else:
                self.alarm_duration += self.record_interval
        else:
            if self.alarm_triggered:
                self.alarm_triggered = False
                self.update_alarm_indicator(False)
                messagebox.showinfo("报警解除", f"声级恢复正常\n持续时间: {self.alarm_duration:.1f}秒")
                
    def setup_csv_writer(self):
        """设置CSV写入器"""
        filename = f"sound_level_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.csv_file = open(filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['时间戳', '声级(dB)'])
        self.status_var.set(f"记录中 - 数据保存到: {filename}")
        
    def calculate_db(self, audio_data):
        """计算分贝值"""
        rms = np.sqrt(np.mean(np.square(audio_data)))
        pressure = rms / 32768.0
        return 20 * math.log10(pressure / self.reference_pressure) if pressure > self.reference_pressure else 0
        
    def update_plot(self):
        """更新图形"""
        if len(self.db_values) > 0:
            self.line.set_data(
                np.arange(len(self.db_values)) * self.record_interval,
                list(self.db_values)
            )
            
            if len(self.db_values) >= self.max_records:
                self.ax.set_xlim(
                    (len(self.db_values) - self.max_records) * self.record_interval,
                    len(self.db_values) * self.record_interval
                )
                
            self.canvas.draw()
            
    def record_data(self, db):
        """记录数据"""
        now = datetime.now()
        timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
        self.records.append((timestamp, db))
        self.timestamps.append(now)
        self.db_values.append(db)
        
        if self.csv_writer:
            self.csv_writer.writerow([timestamp, f"{db:.2f}"])
            self.csv_file.flush()
            
    def audio_processing_loop(self):
        """音频处理主循环"""
        last_record_time = time.time()
        
        while self.is_running:
            # 读取音频数据
            data = self.stream.read(self.CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            
            # 计算分贝值
            db = self.calculate_db(audio_data)
            
            # 更新UI
            self.db_var.set(f"{db:.2f} dB")
            
            # 定期记录数据
            current_time = time.time()
            if current_time - last_record_time >= self.record_interval:
                self.record_data(db)
                self.check_alarm(db)
                self.update_plot()
                last_record_time = current_time
                
            # 防止UI冻结
            self.root.update_idletasks()
            
    def start(self):
        """启动声级计"""
        if not self.is_running:
            self.is_running = True
            self.setup_csv_writer()
            
            self.stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            
            # 在单独线程中运行音频处理
            self.audio_thread = Thread(target=self.audio_processing_loop)
            self.audio_thread.start()
            
    def stop(self):
        """停止声级计"""
        if self.is_running:
            self.is_running = False
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.csv_file:
                self.csv_file.close()
            self.status_var.set("已停止")
            
    def on_close(self):
        """处理窗口关闭事件"""
        self.stop()
        self.p.terminate()
        self.root.destroy()
        
if __name__ == "__main__":
    app = AdvancedSoundLevelMeter()
    app.root.mainloop()