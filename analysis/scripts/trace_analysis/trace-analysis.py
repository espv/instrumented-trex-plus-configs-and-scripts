
import re
import os
import errno
from pathlib import Path
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from openpyxl_templates import TemplatedWorkbook
from openpyxl_templates.table_sheet import TableSheet
from openpyxl_templates.table_sheet.columns import CharColumn, IntColumn
import numpy as np
import numpy_indexed as npi
from matplotlib import pyplot as plt
import seaborn as sns

trace_fn = None

FIRST_TRACEID = 1

np.set_printoptions(edgeitems=30, linewidth=100000,
                    formatter=dict(float=lambda x: "%.3g" % x))


class TraceSheet(TableSheet):
    traceId = CharColumn()
    cpuId = CharColumn()
    threadId = CharColumn()
    timestamp = CharColumn()


class TraceIdheet(TableSheet):
    traceIdFrom = CharColumn()
    traceIdTo = CharColumn()
    cpuId = CharColumn()
    threadId = CharColumn()
    timestamp = IntColumn()


class TraceWorkBook(TemplatedWorkbook):
    regular_trace_entries = TraceSheet()
    traceid_trace_entries = TraceIdheet()


class TraceEntry():
    def __init__(self, traceId, cpuId, threadId, timestamp, cur_prev_time_diff):
        self.traceId = traceId
        self.cpuId = cpuId
        self.threadId = threadId
        self.timestamp = timestamp
        self.cur_prev_time_diff = cur_prev_time_diff


class Trace():
    def __init__(self, trace, output_fn):
        self.rows = []
        self.raw_rows = []
        self.trace = trace
        self.wb = TraceWorkBook()
        self.output_fn = output_fn
        self.numpy_rows = None
    
    def collect_data(self):
        previous_time = 0
        for l in self.trace:
            split_l = re.split('\t|\n', l)
            traceId = int(split_l[0])
            cpuId = int(split_l[1])
            threadId = int(split_l[2])
            t = int(split_l[3])
            if traceId == FIRST_TRACEID:
                previous_time = t
            self.rows.append(TraceEntry(traceId, threadId, cpuId, t, t-previous_time))
            previous_time = t

        self.numpy_rows = np.array([[te.traceId, te.threadId, te.cpuId, te.timestamp, te.cur_prev_time_diff] for te in self.rows])
        print(self.numpy_rows)
        print("\n")
        grouped_by_traceId = npi.group_by(self.numpy_rows[:, 0]).split(self.numpy_rows[:, :])
        for r in grouped_by_traceId:
            print(r, "\n")

        y_hist = []
        for group in grouped_by_traceId:
            diffs = np.array([r[4] for r in group])
            y_hist.append(diffs)

        trace_file_id = re.split('traces/|\.trace', self.trace.name)[1]
        try:
            os.mkdir('output/'+trace_file_id)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir('output/'+trace_file_id):
                pass
            else:
                raise
        y = [[g[i][4] for i in range(len(g))] for g in grouped_by_traceId]
        fig, ax = plt.subplots()
        ax.plot(np.arange(len(grouped_by_traceId)), np.asarray([np.percentile(fifty, 50) for fifty in y]), label='50th percentile')
        ax.plot(np.arange(len(grouped_by_traceId)), np.asarray([np.percentile(fourty, 40) for fourty in y]), label='40th percentile')
        ax.plot(np.arange(len(grouped_by_traceId)), np.asarray([np.percentile(thirty, 30) for thirty in y]), label='30th percentile')
        ax.plot(np.arange(len(grouped_by_traceId)), np.asarray([np.percentile(twenty, 20) for twenty in y]), label='20th percentile')
        ax.plot(np.arange(len(grouped_by_traceId)), np.asarray([np.percentile(seventy, 70) for seventy in y]), label='70th percentile')
        ax.plot(np.arange(len(grouped_by_traceId)), np.asarray([np.percentile(eighty, 80) for eighty in y]), label='80th percentile')
        ax.plot(np.arange(len(grouped_by_traceId)), np.asarray([np.percentile(sixty, 60) for sixty in y]), label='60th percentile')
        ax.plot(np.arange(len(grouped_by_traceId)), np.asarray([np.percentile(ten, 10) for ten in y]), label='10th percentile')
        ax.plot(np.arange(len(grouped_by_traceId)), np.asarray([np.percentile(one, 1) for one in y]), label='1th percentile')
        ax.plot(np.arange(len(grouped_by_traceId)), np.asarray([np.percentile(ninety, 90) for ninety in y]), label='90th percentile')
        ax.plot(np.arange(len(grouped_by_traceId)), np.asarray([np.percentile(ninetynine, 99) for ninetynine in y]), label='99h percentile')
        plt.title("Processing delay percentiles")
        plt.xlabel("Processing stage")
        plt.ylabel("Processing delay")
        fig.savefig('output/'+trace_file_id+'/percentiles.png')
        plt.show()
        plt.cla()

        flattened_y = np.hstack(np.asarray([np.asarray(e) for e in y]).flatten())
        x = []
        for i, e in enumerate(y):
            for _ in e:
                x.append(i)

        plt.title("Processing delay scatter plot")
        plt.xlabel("Processing stage")
        plt.ylabel("Processing delay")
        fig = plt.scatter(x, flattened_y).get_figure()
        fig.savefig('output/'+trace_file_id+'/scatter.png')
        plt.show()

        for i, group in enumerate(y_hist):
            try:
                plt.title("Normalized processing delay histogram for processing stage "+str(i))
                plt.xlabel("Processing delay")
                plt.ylabel("Occurrences ratio")
                sns_plot = sns.distplot(group)
                fig = sns_plot.get_figure()
                fig.savefig('output/'+trace_file_id+'/processing-stage-'+str(i)+'.png')
                plt.show()
            except np.linalg.linalg.LinAlgError:
                pass

    def regular_as_xlsx(self):
        self.wb.regular_trace_entries.write(
            title="Trace",
            objects=((te.traceId, te.cpuId, te.threadId, te.timestamp) for te in self.rows)
        )

        self.wb.save(self.output_fn)

    def traceid_as_xlsx(self):
        self.wb.traceid_trace_entries.write(
            title="Trace ID analytics",
            objects=()
        )

        self.wb.save(self.output_fn)


class TestApp(App):

    def __init__(self):
        super(TestApp, self).__init__()
        content = Button(text='Success')
        self.popup = Popup(title='Analysis finished', content=content,
                           auto_dismiss=True)
        content.bind(on_press=self.popup.dismiss)
        self.bl = BoxLayout(orientation='vertical')

    def select_trace_file(self, instance):
        selected_tb = None
        for c in self.bl.children:
            if isinstance(c, ToggleButton) and c.state == 'down':
                selected_tb = c
                break
        if selected_tb is not None:
            trace_file = open('../../traces/'+selected_tb.text, 'r')
            trace = Trace(trace_file, "processed-"+trace_file.name.split(".")[0]+".xlsx")
            trace.collect_data()
            trace.regular_as_xlsx()
            trace.traceid_as_xlsx()

        self.popup.open()

    def build(self):
        self.bl.add_widget(Label(text='Select trace file to analyze'))
        pathlist = [(os.stat('../../traces/'+p.name).st_mtime, p.name) for p in Path('../../traces').glob('**/*.trace')]
        pathlist.sort(key=lambda s: s[0])
        for i, (time, fn) in enumerate(pathlist):
            # print(path_in_str)
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

TestApp().run()
