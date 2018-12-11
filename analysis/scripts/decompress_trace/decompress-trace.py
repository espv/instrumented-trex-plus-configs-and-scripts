
import os
from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton

# FSMs

# Services (tasks):

# Queues:

trace_id_to_CSEW_events = {
    '0': 	"HIRQENTRY 0 1 [CPU_CYCLES] 1 0 0 interruptfifop_fired s\n",

    '1':    "TEMPSYNCH 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n" +
            "PEUSTART 0 1 [CPU_CYCLES] 1 2 0 (TEMP) s\n" +
            "WAITCOMPL 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n",

    '2': 	"TEMPSYNCH 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n" +
            "PEUSTART 0 1 [CPU_CYCLES] 1 5 0 (TEMP) s\n" +
            "WAITCOMPL 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n",

    '3': 	"HIRQEXIT 0 1 [CPU_CYCLES] 1 0 0 interruptfifop_fired s\n",

    '4': 	"HIRQENTRY 0 2 [CPU_CYCLES] 2 0 0 readDoneLength s\n" +
            "COMPL 0 2 [CPU_CYCLES] 1 0 0 (TEMP) readDoneLength\n",

    '5': 	"TEMPSYNCH 0 2 [CPU_CYCLES] 2 0 1 (TEMP) readDoneFcf\n" +
            "PEUSTART 0 2 [CPU_CYCLES] 2 3 0 (TEMP) s\n" +
            "WAITCOMPL 0 2 [CPU_CYCLES] 2 0 1 (TEMP) readDoneFcf\n",

    '6': 	"HIRQEXIT 0 2 [CPU_CYCLES] 2 0 0 readDoneLength s\n",

    '7': 	"HIRQENTRY 0 3 [CPU_CYCLES] 3 0 0 readDoneFcf s\n" +
            "COMPL 0 3 [CPU_CYCLES] 1 0 0 (TEMP) readDoneFcf\n",

    '8': 	"TEMPSYNCH 0 3 [CPU_CYCLES] 3 0 1 (TEMP) readDonePayload\n" +
            "PEUSTART 0 3 [CPU_CYCLES] 3 4 0 (TEMP) s\n" +
            "WAITCOMPL 0 3 [CPU_CYCLES] 3 0 1 (TEMP) readDonePayload\n",

    '9': 	"HIRQEXIT 0 3 [CPU_CYCLES] 3 0 0 readDoneFcf s\n",

    '10': 	"HIRQENTRY 0 4 [CPU_CYCLES] 4 0 0 readDonePayload s\n" +
             "COMPL 0 4 [CPU_CYCLES] 1 0 0 (TEMP) readDonePayload\n",

    '11':	"SRVQUEUE 0 4 [CPU_CYCLES] 0 2 0 receiveDone_task 0\n" +
             "HIRQEXIT 0 4 [CPU_CYCLES] 4 0 0 readDonePayload s\n",

    '12': "",  # "SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 receiveDone_task s\n"

    '13': 	"QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 receiveDone_task s\n",

    '14': 	"QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 receiveDone_task s\n",

    '15': 	"PKTQUEUE 0 0 [CPU_CYCLES] 0 1 0 receiveDone_task s\n",

    '41': 	"SRVQUEUE 0 0 [CPU_CYCLES] 0 2 0 sendTask 0\n",

    '16': 	"",  # "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 receiveDone_task s\n"

    '17': 	"",  # "SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 sendTask s\n"

    '18': 	"QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask s\n",

    '19': 	"QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask s\n",

    '20': 	"PKTQUEUE 0 0 [CPU_CYCLES] 1 1 0 sendTask s\n",

    # (TEMP) was 2_synch
    '21': 	"TEMPSYNCH 0 0 [CPU_CYCLES] 0 0 1 (TEMP) sendDone\n" +
            "PEUSTART 0 0 [CPU_CYCLES] 0 7 0 (TEMP) s\n" +
            "WAITCOMPL 0 0 [CPU_CYCLES] 0 0 1 (TEMP) sendDone\n",

    '22': "",  # "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 sendTask s\n"

    # (TEMP) was 2_synch
    '23': 	"HIRQENTRY 0 7 [CPU_CYCLES] 7 0 0 sendDone s\n" +
            "COMPL 0 7 [CPU_CYCLES] 1 0 0 (TEMP) sendDone\n" +
            "SRVQUEUE 0 7 [CPU_CYCLES] 0 2 0 sendDone_task s\n" +
            "HIRQEXIT 0 7 [CPU_CYCLES] 7 0 0 sendDone s\n",

    '24': 	"HIRQENTRY 0 5 [CPU_CYCLES] 5 0 0 readDoneAckLength s\n" +
             "COMPL 0 5 [CPU_CYCLES] 1 0 0 (TEMP) readDoneAckLength\n",

    '25': 	"TEMPSYNCH 0 5 [CPU_CYCLES] 1 0 1 (TEMP) readDoneAck\n" +
            "PEUSTART 0 5 [CPU_CYCLES] 5 6 0 (TEMP) s\n" +
            "WAITCOMPL 0 5 [CPU_CYCLES] 1 0 1 (TEMP) readDoneAckLength\n",

    '26': 	"HIRQEXIT 0 5 [CPU_CYCLES] 5 0 0 readDoneAckLength s\n",

    '27': 	"",

    '28': 	"",  # "HIRQEXIT 0 0 [CPU_CYCLES] 6 0 0 readDoneAckLength s\n"

    '29': 	"HIRQENTRY 0 0 [CPU_CYCLES] 6 0 0 readDoneAckPayload s\n" +
            "COMPL 0 6 [CPU_CYCLES] 1 0 0 (TEMP) readDoneAckPayload\n",

    '30': 	"HIRQEXIT 0 6 [CPU_CYCLES] 6 0 0 readDoneAckPayload s\n",

    '31': 	"",  # "SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 sendDone_task s\n"

    '32': 	"",  # "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 sendDone_task s\n"

    '33': 	"CTXSW 0 0 [CPU_CYCLES] 0 0 0 0 s\n",
    # "SRVENTRY 0 0 [CPU_CYCLES] 0 0 0 scheduler_tasks s\n"# +
    # "SRVENTRY 0 0 [CPU_CYCLES] 0 0 0 scheduler_tasks s\n" +
    # "LOOPSTART 0 0 [CPU_CYCLES] 0 0 0 2 task_loop\n"

    '34': 	"",  # "CTXSW 0 0 [CPU_CYCLES] 0 0 0 0 s\n" + "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop s\n"

    '35': 	"",  # "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop s\n" +
    # "LOOPSTART 0 0 [CPU_CYCLES] 0 0 0 4 s\n"

    '36': 	"",  # "TTWAKEUP 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" +
    # "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" +
    # "LOOPRSTART 0 0 [CPU_CYCLES] 0 0 0 4 s\n"

    '37': 	"",  # "TTWAKEUP 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" +
    # "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" +
    # "LOOPSTOP 0 0 [CPU_CYCLES] 0 0 0 4 s\n"

    '38': 	"SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 SERVICE_PLACEHOLDER s\n" + "LOOPRSTART 0 0 [CPU_CYCLES] 0 0 0 2 task_loop\n",

    '39': 	"SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 SERVICE_PLACEHOLDER s\n",

    '40': 	"PKTQUEUE 0 0 [CPU_CYCLES] 0 3 0 sendTask s\n",

    '42': 	"",

    '43': 	"",

    '44': 	"",

    '45': 	"",

    '46': 	"",  # "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 sendDone_task s\n"

    '47':  	"",

    '71': 	"QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask empty\n",

    '91': 	"QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask notempty\n"
}

printed = False


def eid_to_event(e, cycles):
	res = trace_id_to_CSEW_events.get(e, "")

	return res.replace("[CPU_CYCLES]", str(cycles), -1)


class TestApp(App):

	def __init__(self):
		super(TestApp, self).__init__()
		content = Button(text='Success')
		self.popup = Popup(title='Decompression finished', content=content)
		content.bind(on_press=self.popup.dismiss)
		self.bl = BoxLayout(orientation='vertical')

	def select_trace_file(self, _):
		selected_tb = None
		for c in self.bl.children:
			if isinstance(c, ToggleButton) and c.state == 'down':
				selected_tb = c
				break
		if selected_tb is not None:
			trace_file = open('../../traces/'+selected_tb.text, 'r')

			output_file = open("output/processed-"+selected_tb.text, "w")
			output_file.write("EOD\n")
			i = 0
			for l in trace_file:
				line = l.split("\t")
				if len(line) < 2:
					break

				eid = int(line[0])
				i += 1
				cycles = int(line[3])
				output_file.write(eid_to_event(eid, cycles)+"\n")
			output_file.write("H		\n")

		self.popup.open()

	def build(self):
		self.bl.add_widget(Label(text='Select trace file to decompress to CSEM events'))
		path_list = [(os.stat('../../traces/'+p.name).st_mtime, p.name) for p in Path('../../traces').glob('**/*.trace')]
		path_list.sort(key=lambda s: s[0])
		for i, (time, fn) in enumerate(path_list):
			if i == 0:
				self.bl.add_widget(ToggleButton(text=fn, group="trace file", state='down'))
			else:
				self.bl.add_widget(ToggleButton(text=fn, group="trace file"))

		select_button = Button(text="Select")
		select_button.bind(on_press=self.select_trace_file)
		self.bl.add_widget(select_button)
		exit_button = Button(text="Exit")
		exit_button.bind(on_press=lambda _: exit(0))
		self.bl.add_widget(exit_button)
		return self.bl


if __name__ == '__main__':
	TestApp().run()
