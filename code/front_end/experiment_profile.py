"""
Experiment metadata dialog.

Provides a popup window for entering experiment details (brain name,
probes, technician, slide numbers, etc.) which are saved to
experiment_detail.txt in the experiment working directory.

Author: Aixin Zhang
"""
import os
import tkinter as tk
import time
from pytz import timezone
from datetime import datetime
def get_time():
    """Return the current US/Pacific time as a formatted string."""
    time_now = timezone('US/Pacific')
    time = str(datetime.now(time_now))[0:19] + "\n"
    return time


class Exp_profile():
    """Popup dialog for entering and saving experiment metadata.

    Args:
        path: Experiment working directory path.
    """

    def __init__(self,path):
        self.pos_path=path
        self.exp_popup = tk.Tk()
        self.exp_popup.title("Experiment details")
        self.exp_popup.geometry("450x500")
        self.lb1=tk.Label(self.exp_popup,text="Folder name on file:",width=20)
        self.filed1= tk.Entry(self.exp_popup, relief="groove", width=30)
        self.lb2 = tk.Label(self.exp_popup, text="Brain name:", width=20)
        self.filed2 = tk.Entry(self.exp_popup, relief="groove", width=30)
        self.lb3 = tk.Label(self.exp_popup, text="Padlock probes:", width=20)
        self.filed3 = tk.Entry(self.exp_popup, relief="groove", width=30)
        self.lb4 = tk.Label(self.exp_popup, text="Library preparation date:", width=20)
        self.filed4 = tk.Entry(self.exp_popup, relief="groove", width=30)
        self.lb5 = tk.Label(self.exp_popup, text="Technician:", width=20)
        self.filed5 = tk.Entry(self.exp_popup, relief="groove", width=30)
        self.lb6 = tk.Label(self.exp_popup, text="Slide numbers:", width=20)
        self.filed6 = tk.Entry(self.exp_popup, relief="groove", width=30)
        self.lb7 = tk.Label(self.exp_popup, text="Additonal note:", width=20)
        self.stw = tk.scrolledtext.ScrolledText(
            master=self.exp_popup,
            wrap=tk.WORD,
            width=30,
            height=10,
        )
        self.btn = tk.Button(self.exp_popup, text="Save", command=self.save,width=20
                               )
        self.lb1.place(x=20,y=10)
        self.filed1.place(x=160,y=10)
        self.lb2.place(x=20, y=40)
        self.filed2.place(x=160, y=40)
        self.lb6.place(x=20, y=70)
        self.filed6.place(x=160, y=70)
        self.lb3.place(x=20, y=100)
        self.filed3.place(x=160, y=100 )
        self.lb4.place(x=20, y=130)
        self.filed4.place(x=160, y=130 )
        self.lb5.place(x=20, y=160)
        self.filed5.place(x=160, y=160)
        self.lb7.place(x=20, y=190)
        self.stw.place(x=160, y=190)
        self.btn.place(x=120, y=420)
    def save(self):
        """Save all entered metadata to experiment_detail.txt and close dialog."""
        txt=get_time()+"Folder name on file:"+self.filed1.get()+"\n"+"Brain name:"+self.filed2.get()+"\n"+"Slide numbers:"+self.filed6.get()+"\n"+"Padlock probes:"+self.filed3.get()+"\n"+"Library preparation date:"+self.filed4.get()+"\n"+"Technician:"+self.filed5.get() + "\n" +"Additonal note:"+self.stw.get("1.0", tk.END)+ "\n"
        if not os.path.exists(os.path.join(self.pos_path, "experiment_detail.txt")):
            open(os.path.join(self.pos_path, "experiment_detail.txt"), 'w')
        f = open(os.path.join(self.pos_path, "experiment_detail.txt"), "a")
        f.write(txt)
        f.close()
        self.exp_popup.destroy()

