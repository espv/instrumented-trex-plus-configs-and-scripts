
import os

from pathlib import Path
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.uix.label import Label

# FEMs
# - Enqueue packet on cc2420::rx. Check if currently overflow on chip, return if so. Check for overflow, and set flag if so.
#   Start HIRQ-321
# - CALLBACK from readDoneLength
# - CALLBACK from readDoneFcf
# - CALLBACK from readDoneAckLength
# - CALLBACK from sendTask (if successfull) which enqueues an ack, and schedules HIRQ-321 if no thread is currently reading packets.

# Thread 0: task loop and tasks
# Thread 321: InterruptFIFOP.fired, PEUSTART readDoneLength.
# PEUSTART will be followed eventually by a call to a HIRQ, which is readDoneLength in the above case. In a signature,
# the PEUSTART line will include the number of cycles it takes before the HIRQ is called, and the normal. That way,
# it can be modelled accurately when a HIRQ is called.
# Thread 1234: readDoneLength - CALLBACK to schedule readDoneFcf
# Thread 2345: readDoneFcf - CALLBACK to scheule readDonePayload
# Thread 3456: readDonePayload - ENQUEUE SRVQUEUE softirq::rx receiveDone_task
# Thread 4567: readDoneAckLength - CALLBACK to schedule readDoneAckPayload
# Thread 5678: readDoneAckPayload

# Services (tasks):
# - task_loop - DEQUEUE SRVQUEUE softirq::rx
# - receiveDone_task - ENQUEUE SRVQUEUE softirq::rx sendTask, ENQUEUE PKTQUEUE ip::sendinfo, ENQUEUE PKTQUEUE ip::sendpacket
# - sendTask - QUEUECOND to decide whether to drop packet or not, DEQUEUE PKTQUEUE ip::sendinfo, DEQUEUE PKTQUEUE ip::sendpacket, ENQUEUE PKTQUEUE cc2420::tx
# - waitForNextPacket - When finished receiving a packet in readDonePayload or readDoneAckPayload, we call this service.
#   The service can be initialized from a callback function in the ns3 model. For instance, IF cc2420::rxfifo.size > 0, THEN CALL waitForNextPacket.
#   Alternatively, the two HIRQs can end with QUEUECOND cc2420::rx, which causes waitForNextPacket to be called if size > 0, or not if size == 0.

# Queues:
# - ip::sendinfo
# - ip::sendpacket
# - softirq::rx
# - cc2420::rx
# - cc2420::tx

# Thread 0 includes all scheduler / tasks. Since these can be interrupted and currently we don't know of a place
# in code where this can be traced, we prepend all event traces in thread 0 with "CTXSW 0 0 [CPU_CYCLES] 0 0 0 0 s". This
# means that no matter where we're interrupted in thread 0, we will still be able to switch back to thread 0 for the events.

trace_id_to_CSEW_events = {
	'0': "HIRQENTRY 0 1 [CPU_CYCLES] 1 0 0 interruptfifop_fired s\n",

	'1': "TEMPSYNCH 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n" + \
		"PEUSTART 0 1 [CPU_CYCLES] 1 2 0 (TEMP) s\n" + \
		"WAITCOMPL 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n",

	'2': "TEMPSYNCH 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n" + \
		"PEUSTART 0 1 [CPU_CYCLES] 1 5 0 (TEMP) s\n" + \
		"WAITCOMPL 0 1 [CPU_CYCLES] 1 0 1 (TEMP) readDoneLength\n",

	'3': "HIRQEXIT 0 1 [CPU_CYCLES] 1 0 0 interruptfifop_fired s\n",

	'4': "HIRQENTRY 0 2 [CPU_CYCLES] 2 0 0 readDoneLength s\n" + \
		"COMPL 0 2 [CPU_CYCLES] 1 0 0 (TEMP) readDoneLength\n",

	'5': "TEMPSYNCH 0 2 [CPU_CYCLES] 2 0 1 (TEMP) readDoneFcf\n" + \
		"PEUSTART 0 2 [CPU_CYCLES] 2 3 0 (TEMP) s\n" + \
		"WAITCOMPL 0 2 [CPU_CYCLES] 2 0 1 (TEMP) readDoneFcf\n",

	'6': "HIRQEXIT 0 2 [CPU_CYCLES] 2 0 0 readDoneLength s\n",

	'7': "HIRQENTRY 0 3 [CPU_CYCLES] 3 0 0 readDoneFcf s\n" + \
		"COMPL 0 3 [CPU_CYCLES] 1 0 0 (TEMP) readDoneFcf\n",

	'8': "TEMPSYNCH 0 3 [CPU_CYCLES] 3 0 1 (TEMP) readDonePayload\n" + \
		"PEUSTART 0 3 [CPU_CYCLES] 3 4 0 (TEMP) s\n" + \
		"WAITCOMPL 0 3 [CPU_CYCLES] 3 0 1 (TEMP) readDonePayload\n",

	'9': "HIRQEXIT 0 3 [CPU_CYCLES] 3 0 0 readDoneFcf s\n",

	'10': "HIRQENTRY 0 4 [CPU_CYCLES] 4 0 0 readDonePayload s\n" + \
		"COMPL 0 4 [CPU_CYCLES] 1 0 0 (TEMP) readDonePayload\n",

	'11': "SRVQUEUE 0 4 [CPU_CYCLES] 0 2 0 receiveDone_task 0\n" + \
		"HIRQEXIT 0 4 [CPU_CYCLES] 4 0 0 readDonePayload s\n",

	# e39 means that we don't have to record the start of each service / task in each service, but let the scheduler record this event.
	'12': "",# "SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 receiveDone_task s\n"

	'13': "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 receiveDone_task s\n",

	'14': "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 receiveDone_task s\n",

	'15': "PKTQUEUE 0 0 [CPU_CYCLES] 0 1 0 receiveDone_task s\n",

	'41': "SRVQUEUE 0 0 [CPU_CYCLES] 0 2 0 sendTask 0\n",

	'16': "",# "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 receiveDone_task s\n"

	# e39 means that we don't have to record the start of each service / task in each service, but let the scheduler record this event.
	'17': "",# "SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 sendTask s\n"

	'18': "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask s\n",

	'19': "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask s\n",

	'20': "PKTQUEUE 0 0 [CPU_CYCLES] 1 1 0 sendTask s\n",

	# (TEMP) was 2_synch
	'21': "TEMPSYNCH 0 0 [CPU_CYCLES] 0 0 1 (TEMP) sendDone\n" + \
		"PEUSTART 0 0 [CPU_CYCLES] 0 7 0 (TEMP) s\n" + \
		"WAITCOMPL 0 0 [CPU_CYCLES] 0 0 1 (TEMP) sendDone\n",

	'22': "", # "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 sendTask s\n"

	# (TEMP) was 2_synch
	'23': "HIRQENTRY 0 7 [CPU_CYCLES] 7 0 0 sendDone s\n" + \
		"COMPL 0 7 [CPU_CYCLES] 1 0 0 (TEMP) sendDone\n" + \
		"SRVQUEUE 0 7 [CPU_CYCLES] 0 2 0 sendDone_task s\n" + \
		"HIRQEXIT 0 7 [CPU_CYCLES] 7 0 0 sendDone s\n",

	'24': "HIRQENTRY 0 5 [CPU_CYCLES] 5 0 0 readDoneAckLength s\n" + \
		"COMPL 0 5 [CPU_CYCLES] 1 0 0 (TEMP) readDoneAckLength\n",

	'25': "TEMPSYNCH 0 5 [CPU_CYCLES] 1 0 1 (TEMP) readDoneAck\n" + \
		"PEUSTART 0 5 [CPU_CYCLES] 5 6 0 (TEMP) s\n" + \
		"WAITCOMPL 0 5 [CPU_CYCLES] 1 0 1 (TEMP) readDoneAckLength\n",

	'26': "HIRQEXIT 0 5 [CPU_CYCLES] 5 0 0 readDoneAckLength s\n",

	'27': "",

	'28': "",# "HIRQEXIT 0 0 [CPU_CYCLES] 6 0 0 readDoneAckLength s\n"

	'29': "HIRQENTRY 0 0 [CPU_CYCLES] 6 0 0 readDoneAckPayload s\n" + \
		"COMPL 0 6 [CPU_CYCLES] 1 0 0 (TEMP) readDoneAckPayload\n",

	'30': "HIRQEXIT 0 6 [CPU_CYCLES] 6 0 0 readDoneAckPayload s\n",

	# e39 means that we don't have to record the start of each service / task in each service, but let the scheduler record this event.
	'31': "",# "SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 sendDone_task s\n"

	'32': "",# "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 sendDone_task s\n"

	'33': "CTXSW 0 0 [CPU_CYCLES] 0 0 0 0 s\n",
	# "SRVENTRY 0 0 [CPU_CYCLES] 0 0 0 scheduler_tasks s\n"# +
	# "SRVENTRY 0 0 [CPU_CYCLES] 0 0 0 scheduler_tasks s\n" + \
	# "LOOPSTART 0 0 [CPU_CYCLES] 0 0 0 2 task_loop\n"

	'34': "",# "CTXSW 0 0 [CPU_CYCLES] 0 0 0 0 s\n" + "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop s\n"

	'35': "",# "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop s\n" + \
	# "LOOPSTART 0 0 [CPU_CYCLES] 0 0 0 4 s\n"

	'36': "",# "TTWAKEUP 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" + \
	# "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" + \
	# "LOOPRSTART 0 0 [CPU_CYCLES] 0 0 0 4 s\n"

	'37': "",# "TTWAKEUP 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" + \
	# "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 task_loop_wait s\n" + \
	# "LOOPSTOP 0 0 [CPU_CYCLES] 0 0 0 4 s\n"

	# Need to find a way for task loop to initiate task. SRVQUEUE requires name of service. How do we get the service name here?
	'38': "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 SERVICE_PLACEHOLDER s\n" + "LOOPRSTART 0 0 [CPU_CYCLES] 0 0 0 2 task_loop\n",

	# The 1 in this trace means that we are dequeueing a service. The 2 means that we are dequeueing from queue 2, which is softirq::rx.
	'39': "SRVQUEUE 0 0 [CPU_CYCLES] 1 2 0 SERVICE_PLACEHOLDER s\n",

	'40': "PKTQUEUE 0 0 [CPU_CYCLES] 0 3 0 sendTask s\n",

	'42': "",

	'43': "",

	'44': "",

	'45': "",

	'46': "",# "SRVEXIT 0 0 [CPU_CYCLES] 0 0 0 sendDone_task s\n"

	'47':  "",

	'71': "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask empty\n",

	'91': "QUEUECOND 0 0 [CPU_CYCLES] 0 0 0 sendTask notempty\n"
}

printed = False


def eid_to_event(e, cycles):
	res = trace_id_to_CSEW_events.get(e)

	return res.replace("[CPU_CYCLES]", cycles, -1)


class TestApp(App):

	def __init__(self):
		super(TestApp, self).__init__()
		self.bl = BoxLayout(orientation='vertical')

	def select_trace_file(self, instance):
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

				eid = int(l[0])
				i += 1
				cycles = int(l[3])
				output_file.write(eid_to_event(eid, cycles)+"\n")
			output_file.write("H		\n")

	def build(self):
		self.bl.add_widget(Label(text='Select trace file to analyze'))
		pathlist = [(os.stat('../../traces/'+p.name).st_mtime, p) for p in Path('../../traces').glob('**/*.trace')]
		pathlist = sorted(y for (x, y) in sorted(pathlist, key=lambda s: s[0]))
		for i, path in enumerate(pathlist):
			# because path is object not string
			fn = path.name
			# print(path_in_str)
			if i == 0:
				self.bl.add_widget(ToggleButton(text=fn, group="trace file", state='down'))
			else:
				self.bl.add_widget(ToggleButton(text=fn, group="trace file"))

		select_button = Button(text="Select")
		select_button.bind(on_press=self.select_trace_file)
		self.bl.add_widget(select_button)
		return self.bl


if __name__ == '__main__':
	TestApp().run()
	import time
	while True:
		time.sleep(1)
