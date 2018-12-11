
import json
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


class TestApp(App):

    def __init__(self):
        super(TestApp, self).__init__()
        content = Button(text='Success')
        self.popup = Popup(title='Decompression finished', content=content)
        content.bind(on_press=self.popup.dismiss)
        self.bl = BoxLayout(orientation='vertical')
        self.trace_id_to_CSEW_events = {}

    def eid_to_event(self, e, cycles):
        res = self.trace_id_to_CSEW_events.get(e, {}).get('csemEvents', "")

        return res.replace("[CPU_CYCLES]", str(cycles), -1)

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
                output_file.write(self.eid_to_event(eid, cycles)+"\n")
            output_file.write("H        \n")

        self.popup.open()

    def select_traceid_to_csem_events_map_file(self, _):
        selected_tb = None
        for c in self.bl.children:
            if isinstance(c, ToggleButton) and c.state == 'down':
                selected_tb = c
                break
        if selected_tb is not None:
            trace_file = open('trace_decompression_configurations/'+selected_tb.text, 'r')
            json_data=trace_file.read()

            data = json.loads(json_data)
            self.trace_id_to_CSEW_events = data["traceIdsToCSEMEvents"]

        self.bl.clear_widgets(self.bl.children)

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

    def build(self):
        self.bl.add_widget(Label(text='Choose map file from trace IDs to CSEM events'))
        path_list = [(os.stat('trace_decompression_configurations/'+p.name).st_mtime, p.name) for p in Path('trace_decompression_configurations/').glob('**/*.json')]
        path_list.sort(key=lambda s: s[0])
        for i, (time, fn) in enumerate(path_list):
            if i == 0:
                self.bl.add_widget(ToggleButton(text=fn, group="trace ID mapping file", state='down'))
            else:
                self.bl.add_widget(ToggleButton(text=fn, group="trace ID mapping file"))

        select_button = Button(text="Select")
        select_button.bind(on_press=self.select_traceid_to_csem_events_map_file)
        self.bl.add_widget(select_button)
        exit_button = Button(text="Exit")
        exit_button.bind(on_press=lambda _: exit(0))
        self.bl.add_widget(exit_button)
        return self.bl


if __name__ == '__main__':
    TestApp().run()
