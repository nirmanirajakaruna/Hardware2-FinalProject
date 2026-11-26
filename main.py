from machine import Pin, I2C, ADC
from fifo import Fifo
from piotimer import Piotimer
from ssd1306 import SSD1306_I2C
import micropython
import time

micropython.alloc_emergency_exception_buf(200)

class Encoder:
    def __init__(self, rot_a, rot_b):
        self.a = Pin(rot_a, Pin.IN)
        self.b = Pin(rot_b, Pin.IN)
        self.fifo = Fifo(30, typecode='i')
        self.a.irq(handler=self.handler, trigger=Pin.IRQ_RISING, hard=True)

    def handler(self, pin):
        if self.b():
            self.fifo.put(-1)
        else:
            self.fifo.put(1)

i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
oled = SSD1306_I2C(128, 64, i2c)

adc = ADC(Pin(26))
led = Pin(22, Pin.OUT)
sw1 = Pin(8, Pin.IN, Pin.PULL_UP)
rot = Encoder(10, 11)

samples_fifo = Fifo(500, typecode='H')

def adc_callback(timer):
    samples_fifo.put(adc.read_u16())

oled.fill(0)
oled.text("Press SW1", 25, 28)
oled.show()

while sw1.value() == 1:
    time.sleep_ms(20)

timer = Piotimer(mode=Piotimer.PERIODIC, freq=250, callback=adc_callback)

init_samples = []
while len(init_samples) < 500:
    if samples_fifo.has_data():
        init_samples.append(samples_fifo.get())

min_val = min(init_samples)
max_val = max(init_samples)
threshold = (max_val + min_val) // 2

last_peak_time = 0
bpm = 0
prev_sample = init_samples[-1]
plot_data = [32] * 128
plot_index = 0

while True:
    updated = False
    
    while rot.fifo.has_data():
        step = rot.fifo.get()
        step_size = max(1, (max_val - min_val) // 50)
        threshold += step * step_size
        updated = True

    while samples_fifo.has_data():
        val = samples_fifo.get()
        
        if val > threshold:
            led.value(1)
        else:
            led.value(0)

        slope = val - prev_sample
        if val > threshold and slope < 0 and prev_sample > threshold:
            current_time = time.ticks_ms()
            if last_peak_time != 0:
                time_diff = time.ticks_diff(current_time, last_peak_time)
                if 300 < time_diff < 2000:
                    bpm = int(60000 / time_diff)
            last_peak_time = current_time
        
        prev_sample = val

        if max_val > min_val:
            scaled_val = int(((val - min_val) / (max_val - min_val)) * 63)
            if scaled_val < 0: scaled_val = 0
            if scaled_val > 63: scaled_val = 63
            plot_data[plot_index] = 63 - scaled_val
        else:
             plot_data[plot_index] = 32
             
        plot_index += 1
        if plot_index >= 128:
            plot_index = 0
            updated = True

    if updated:
        oled.fill(0)
        oled.text(f"HR: {bpm} BPM", 0, 0)
        
        for i in range(1, 128):
            oled.line(i - 1, plot_data[i - 1], i, plot_data[i], 1)
            
        oled.show()