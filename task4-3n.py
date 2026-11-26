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

def update_display(min_v, max_v, thresh):
    oled.fill(0)
    oled.text(f"min: {min_v}", 0, 8)
    oled.text(f"max: {max_v}", 0, 20)
    oled.text(f"thr: {int(thresh)}", 0, 32)
    if max_v > min_v:
        pct = int(((thresh - min_v) / (max_v - min_v)) * 100)
    else:
        pct = 0
    oled.text(f"%:   {pct}", 0, 44)
    oled.show()

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

update_display(min_val, max_val, threshold)

batch_samples = []

while True:
    updated = False
    
    while rot.fifo.has_data():
        step = rot.fifo.get()
        step_size = max(1, (max_val - min_val) // 50)
        threshold += step * step_size
        updated = True

    while samples_fifo.has_data():
        val = samples_fifo.get()
        batch_samples.append(val)
        
        if val > threshold:
            led.value(1)
        else:
            led.value(0)
            
    if len(batch_samples) >= 500:
        min_val = min(batch_samples)
        max_val = max(batch_samples)
        batch_samples = []
        updated = True
        
    if updated:
        update_display(min_val, max_val, threshold)