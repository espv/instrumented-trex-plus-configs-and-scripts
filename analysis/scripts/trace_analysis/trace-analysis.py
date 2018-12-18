
import errno
import json
import os
import re
from collections import OrderedDict
from pathlib import Path

import numpy as np
import numpy_indexed as npi
import seaborn as sns
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.togglebutton import ToggleButton
from matplotlib import pyplot as plt
from openpyxl import Workbook
from openpyxl_templates import TemplatedWorkbook
from openpyxl_templates.table_sheet import TableSheet
from openpyxl_templates.table_sheet.columns import CharColumn, IntColumn

trace_fn = None

FIRST_trace_id = 1

np.set_printoptions(edgeitems=30, linewidth=100000,
                    formatter=dict(float=lambda x: "%.3g" % x))


class TraceSheet(TableSheet):
    line_nr = IntColumn()
    trace_id = CharColumn()
    cpu_id = CharColumn()
    thread_id = CharColumn()
    timestamp = CharColumn()
    time_diff = IntColumn()
    rdtsc = IntColumn()
    rdtsc_diff = IntColumn()


class TraceIdSheet(TableSheet):
    line_nr = IntColumn()
    trace_idFrom = CharColumn()
    trace_idTo = CharColumn()
    cpu_id = CharColumn()
    thread_id = CharColumn()
    timestamp = IntColumn()
    time_diff = IntColumn()
    rdtsc = IntColumn()
    rdtsc_diff = IntColumn()


class TraceWorkBook(TemplatedWorkbook):
    regular_trace_entries = TraceSheet()
    trace_id_trace_entries = TraceIdSheet()


class TraceEntry(object):
    def __init__(self, line_nr, trace_id, cpu_id, thread_id, timestamp, cur_prev_time_diff, rdtsc, cur_prev_rdtsc_diff):
        self.line_nr = line_nr
        self.trace_id = trace_id
        self.cpu_id = cpu_id
        self.thread_id = thread_id
        self.timestamp = timestamp
        self.cur_prev_time_diff = cur_prev_time_diff
        self.rdtsc = rdtsc
        self.cur_prev_rdtsc_diff = cur_prev_rdtsc_diff


class Trace(object):
    def __init__(self, trace, output_fn, possible_trace_event_transitions, reverse_possible_trace_event_transitions):
        self.rows = []
        self.raw_rows = []
        self.trace = trace
        self.wb = Workbook(write_only=True)  #TraceWorkBook(write_only=True)
        self.output_fn = output_fn
        self.possible_trace_event_transitions = possible_trace_event_transitions
        self.reverse_possible_trace_event_transitions = reverse_possible_trace_event_transitions
        self.numpy_rows = None
    
    def collect_data(self):
        previous_times = {}
        previous_rdtscs = {}
        for line_nr, l in enumerate(self.trace):
            split_l = re.split('[\t\n]', l)
            trace_id = int(split_l[0])
            previous_trace_id = self.reverse_possible_trace_event_transitions.get(str(trace_id))
            previous_time = previous_times.get(str(previous_trace_id), [0]).pop()
            previous_rdtsc = previous_rdtscs.get(str(previous_trace_id), [0]).pop()
            cpu_id = int(split_l[1])
            thread_id = int(split_l[2])
            t = int(split_l[3])
            rdtsc = int(split_l[4])
            if trace_id == FIRST_trace_id:
                previous_time = t
            self.rows.append(TraceEntry(line_nr, trace_id, thread_id, cpu_id, t, t-previous_time, rdtsc, rdtsc-previous_rdtsc))
            previous_times.setdefault(str(trace_id), []).append(t)
            previous_rdtscs.setdefault(str(trace_id), []).append(rdtsc)

    def regular_as_xlsx(self, pb, popup, bl, btn):
        ws = self.wb.create_sheet("Trace")
        trace_file_id = re.split('traces/|[.]trace', self.trace.name)[1]
        try:
            os.mkdir('output/'+trace_file_id)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir('output/'+trace_file_id):
                pass
            else:
                raise

        self.max = len(self.rows)+len(self.rows)*1.6
        self.cnt = 0

        def update_bar(_):
            if self.cnt >= len(self.rows):
                try:
                    self.wb.save('output/'+trace_file_id+'/'+self.output_fn)
                except FileNotFoundError:
                    pass
                popup.open()
                self.cnt = self.max
                bl.add_widget(btn, 3)
                bl.clear_widgets([pb])
                return
            else:
                self.update_bar_trigger()

            pb.value = self.cnt
            te = self.rows[self.cnt]
            self.cnt += 1
            row = [te.line_nr, te.trace_id, te.thread_id,  te.cpu_id, te.timestamp, te.cur_prev_time_diff, te.rdtsc, te.cur_prev_rdtsc_diff]
            ws.append(row)

        self.update_bar_trigger = Clock.create_trigger(update_bar, -1)
        Clock.max_iteration = 100

        self.update_bar_trigger()

    def as_plots(self):
        self.numpy_rows = np.array([[te.trace_id, te.thread_id, te.cpu_id, te.timestamp, te.cur_prev_time_diff, te.cur_prev_rdtsc_diff] for te in self.rows])
        print(self.numpy_rows)
        print("\n")
        tmp_grouped_by_trace_id = npi.group_by(self.numpy_rows[:, 0]).split(self.numpy_rows[:, :])
        for r in tmp_grouped_by_trace_id:
            print(r, "\n")

        grouped_by_trace_id = []

        def get_index_in_dag(event_type, dag):
            for i, (k, _) in enumerate(dag.items()):
                if str(event_type) == k:
                    return i
            return -1
        for group_tmp in tmp_grouped_by_trace_id:
            group_tmp_index = get_index_in_dag(group_tmp[0][0], self.possible_trace_event_transitions)
            grouped_by_trace_id.insert(group_tmp_index, group_tmp)

        y_hist = []
        for group in grouped_by_trace_id:
            diffs = np.array([r[4] for r in group])
            y_hist.append(diffs)

        trace_file_id = re.split('traces/|[.]trace', self.trace.name)[1]
        try:
            os.mkdir('output/'+trace_file_id)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir('output/'+trace_file_id):
                pass
            else:
                raise
        y = [[g[i][4] for i in range(len(g))] for g in grouped_by_trace_id]
        fig, ax = plt.subplots()
        x = np.arange(len(grouped_by_trace_id))
        xticks = [g[0][0] for i, g in enumerate(grouped_by_trace_id) if len(g) > 0 and len(g[0]) > 0]
        plt.xticks(x, xticks)
        ax.plot(x, np.asarray([np.percentile(fifty, 50) for fifty in y]), label='50th percentile')
        ax.plot(x, np.asarray([np.percentile(fourty, 40) for fourty in y]), label='40th percentile')
        ax.plot(x, np.asarray([np.percentile(thirty, 30) for thirty in y]), label='30th percentile')
        ax.plot(x, np.asarray([np.percentile(twenty, 20) for twenty in y]), label='20th percentile')
        ax.plot(x, np.asarray([np.percentile(seventy, 70) for seventy in y]), label='70th percentile')
        ax.plot(x, np.asarray([np.percentile(eighty, 80) for eighty in y]), label='80th percentile')
        ax.plot(x, np.asarray([np.percentile(sixty, 60) for sixty in y]), label='60th percentile')
        ax.plot(x, np.asarray([np.percentile(ten, 10) for ten in y]), label='10th percentile')
        ax.plot(x, np.asarray([np.percentile(one, 1) for one in y]), label='1th percentile')
        ax.plot(x, np.asarray([np.percentile(ninety, 90) for ninety in y]), label='90th percentile')
        ax.plot(x, np.asarray([np.percentile(ninetynine, 99) for ninetynine in y]), label='99h percentile')
        plt.title("Processing delay percentiles")
        plt.xlabel("Processing stage")
        plt.ylabel("Processing delay")
        fig.savefig('output/'+trace_file_id+'/percentiles.png')
        plt.show()
        plt.cla()

        flattened_y = np.hstack(np.asarray([np.asarray(e) for e in y]).flatten())
        x = []
        #xticks = []
        for i, e in enumerate(y):
            for _ in e:
                x.append(i)
                #xticks.append(grouped_by_trace_id[i][0][0])

        plt.title("Processing delay scatter plot")
        plt.xlabel("Processing stage")
        plt.ylabel("Processing delay")
        #unique, index = np.unique(xticks, return_inverse=True)
        fig = plt.scatter(x, flattened_y).get_figure()

        plt.xticks(range(len(xticks)), xticks)
        fig.savefig('output/'+trace_file_id+'/scatter.png')
        plt.show()

        for i, group in enumerate(y_hist[1:]):
            try:
                proc_stage = str(grouped_by_trace_id[i+1][0][0])
                proc_stage = str(grouped_by_trace_id[i][0][0]) + "-" + proc_stage
                plt.title("Normalized processing delay histogram for processing stage " + proc_stage)
                plt.xlabel("Processing delay")
                plt.ylabel("Occurrences ratio")
                sns_plot = sns.distplot(group)
                plt.xlim([0, np.percentile(group, 99)])
                fig = sns_plot.get_figure()
                fig.savefig('output/'+trace_file_id+'/processing-stage-'+proc_stage+'.png')
                plt.show()
            except np.linalg.linalg.LinAlgError:
                pass


class TestApp(App):

    def __init__(self):
        super(TestApp, self).__init__()
        content = Button(text='Success')
        self.popup = Popup(title='Analysis finished', content=content,
                           auto_dismiss=True)
        content.bind(on_press=self.popup.dismiss)
        self.bl = BoxLayout(orientation='vertical')
        self.possible_trace_event_transitions = {}
        self.reverse_possible_trace_event_transitions = {}
        self.trace_id_to_CSEW_events = {}
        self.selected_trace_tb = None
        self.trace_file = None
        self.trace = None

    def gen_plots(self, _):
        if self.trace is not None:
            self.trace.as_plots()
        self.popup.open()

    def gen_xlsx(self, btn: Button):
        if self.trace is not None:
            pb = ProgressBar(max=len(self.trace.rows)*1.6, value=0)
            self.bl.clear_widgets([btn])
            self.bl.add_widget(pb, 3)
            self.trace.regular_as_xlsx(pb, self.popup, self.bl, btn)

    def select_trace_file(self, _):
        self.selected_trace_tb = None
        for c in self.bl.children:
            if isinstance(c, ToggleButton) and c.state == 'down':
                self.selected_trace_tb = c
                break

        self.bl.clear_widgets(self.bl.children)

        self.bl.add_widget(Label(text='Choose what to do with trace '+self.selected_trace_tb.text))
        gen_plots_btn = Button(text="Analyze data and generate plots")
        gen_plots_btn.bind(on_press=self.gen_plots)
        self.bl.add_widget(gen_plots_btn)
        gen_xlsx_btn = Button(text="Analyze data and export to excel")
        gen_xlsx_btn.bind(on_press=self.gen_xlsx)
        self.bl.add_widget(gen_xlsx_btn)
        decomp_trace_btn = Button(text="Decompress trace")
        decomp_trace_btn.bind(on_press=self.decompress_trace)
        self.bl.add_widget(decomp_trace_btn)
        back_btn = Button(text="Back")
        back_btn.bind(on_press=self.select_trace_to_analyze)
        self.bl.add_widget(back_btn)
        exit_btn = Button(text="Exit")
        exit_btn.bind(on_press=lambda _: exit(0))
        self.bl.add_widget(exit_btn)

        self.trace_file = open('../../traces/'+self.selected_trace_tb.text, 'r')
        self.trace = Trace(self.trace_file, self.selected_trace_tb.text.split(".trace")[0]+".xlsx", self.possible_trace_event_transitions, self.reverse_possible_trace_event_transitions)
        self.trace.collect_data()

    def eid_to_event(self, e, cycles):
        res = self.trace_id_to_CSEW_events.get(e, {}).get('csemEvents', "")

        return res.replace("[CPU_CYCLES]", str(cycles), -1)

    def decompress_trace(self, _):
        if self.trace_file is not None:
            self.trace_file = open('../../traces/'+self.selected_trace_tb.text, 'r')

            output_file = open("output/processed-"+self.selected_trace_tb.text, "w")
            output_file.write("EOD\n")
            i = 0
            for l in self.trace_file:
                line = l.split("\t")
                if len(line) < 2:
                    break

                eid = int(line[0])
                i += 1
                cycles = int(line[3])
                output_file.write(self.eid_to_event(eid, cycles)+"\n")
            output_file.write("H        \n")

        self.popup.open()

    def select_trace_to_analyze(self, _):
        self.bl.clear_widgets(self.bl.children)
        self.bl.add_widget(Label(text='Select trace file to analyze'))
        path_list = [(os.stat('../../traces/'+p.name).st_mtime, p.name) for p in Path('../../traces').glob('**/*.trace')]
        path_list.sort(key=lambda s: s[0])
        for i, (time, fn) in enumerate(path_list):
            if i == 0:
                self.bl.add_widget(ToggleButton(text=fn, group="trace file", state='down'))
            else:
                self.bl.add_widget(ToggleButton(text=fn, group="trace file"))

        select_button = Button(text="Select")
        select_button.bind(on_press=self.select_trace_file)
        exit_button = Button(text="Exit")
        exit_button.bind(on_press=lambda _: exit(0))
        self.bl.add_widget(select_button)
        self.bl.add_widget(exit_button)
        return self.bl

    def selected_traceid_to_csem_events_map_file(self, _):
        selected_tb = None
        for c in self.bl.children:
            if isinstance(c, ToggleButton) and c.state == 'down':
                selected_tb = c
                break
        if selected_tb is not None:
            trace_file = open('../decompress_trace/trace_decompression_configurations/'+selected_tb.text, 'r')
            json_data = trace_file.read()

            data = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(json_data)
            self.possible_trace_event_transitions = data["possibleTransitions"]  # A trace Id can be followed by one or more trace Ids
            for k, v in self.possible_trace_event_transitions.items():
                for a in v:
                    self.reverse_possible_trace_event_transitions[a] = k  # Assume that a given trace Id can only be preceeded by one trace Id

        return self.select_trace_to_analyze(_)

    def build(self):
        self.bl.add_widget(Label(text='Choose map file from trace IDs to CSEM events'))
        path_list = [(os.stat('../decompress_trace/trace_decompression_configurations/'+p.name).st_mtime, p.name) for p in Path('../decompress_trace/trace_decompression_configurations/').glob('**/*.json')]
        path_list.sort(key=lambda s: s[0])
        for i, (time, fn) in enumerate(path_list):
            if i == 0:
                self.bl.add_widget(ToggleButton(text=fn, group="trace ID mapping file", state='down'))
            else:
                self.bl.add_widget(ToggleButton(text=fn, group="trace ID mapping file"))

        select_button = Button(text="Select")
        select_button.bind(on_press=self.selected_traceid_to_csem_events_map_file)
        self.bl.add_widget(select_button)
        exit_button = Button(text="Exit")
        exit_button.bind(on_press=lambda _: exit(0))
        self.bl.add_widget(exit_button)
        return self.bl


if __name__ == '__main__':
    TestApp().run()
