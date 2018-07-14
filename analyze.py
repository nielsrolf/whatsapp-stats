import datetime as dt
import pdb
from collections import OrderedDict
from matplotlib import pyplot as plt
import numpy as np
import os
from sklearn.svm import SVR

"""
Plots:
    - How many messages per day?
    - How many words per day?
    - How often does someone start a convo (first message after some threshhold)
    - How often does a sequence occur? (eg a certain smiley)
    - message frequency per hour
    - how many words per message
    - average length of convos
    - average response time
Todo:
    - most frequent words
"""

CONV_PATH = 'cemre.txt'
SEQUENCES = ["nice", ":)", ":(", "fuck", "sorry"]


CONV_START_THRESHOLD = 20 # minutes

try: os.mkdir("plots")
except: pass

class Message():
    def __init__(self, line, pre):
        self.skip = False # flag if this is an actual message
        try:
            self.send, line = self.get_time(line)
        except ValueError:
            pre.add(line)
            self.skip = True
            return
        try:
            self.author, line = self.get_author(line)
        except ValueError:
            # it's a whatsapp anouncement
            self.skip = True 
            return

        words = line.lower().split()
        self.text = ' '.join(words)
        self.words_count = len(words)
        try:
            self.time_since_last = (self.send - pre.send).total_seconds()
            self.convo_start = self.time_since_last > CONV_START_THRESHOLD*60
        except AttributeError: # first message
            self.time_since_last = 0
            self.convo_start = True

    def get_time(self, line):
        date_str, line = line[:15], line[18:]
        send = dt.datetime.strptime(date_str, '%d.%m.%y, %H:%M')
        return send, line

    def get_author(self, line):
        author, line = line.split(":", 1)
        return author, line

    def add(self, line):
        words = line.lower().split()
        self.text += ' '.join(words)
        self.words_count += len(words)


with open(CONV_PATH, 'r') as file:
    lines = file.readlines()

messages = [None]
for line in lines:
    msg = Message(line, messages[-1])
    if not msg.skip:
        messages.append(msg)
messages = messages[1:]

"""
Now comes the part to analyze the messages. Here is how it goes

Stat:
    bundles a way to extract and aggregate values.
    Acts like a method that applies both to a list of messages

ApplyStat:
    takes the messages and a statistic, and implements the logic to run it
    the .run method takes a group_by method, that maps messages onto their groups
    and returns a list of keys (the groups) and a list of values (the statistics of that group)

Aggregate:
    bundles a method to group messages and plot them
    This is because the type of the keys (e.g. categorical or timestamps) 
    determines how the plot should look like

    __call__ makes it act like the original group_by method
"""


class Stat():
    """
    A way to process and a way to aggregate belongs together
    """
    def __init__(self, process_msg, aggregate, name):
        self.process_msg, self.aggregate, self.name = process_msg, aggregate, name

    def __call__(self, messages):
        results = []
        for msg in messages:
            v = self.process_msg(msg)
            results.append(v)
        return self.aggregate(results)


class ApplyStat():
    def __init__(self, messages, stat):  #process_msg, aggregate):
        self.messages = messages
        #self.stat = Stat(process_msg, aggregate)
        self.stat = stat

    def run(self, group_by):
        """
        group by: return a key and analyze all messages with the same key in a group
        """
        groups = OrderedDict()
        for msg in self.messages:
            key = group_by(msg)
            try:
                groups[key] = groups.get(key, []) + [msg]
            except Exception as e:
                print(type(e), e)
                pdb.set_trace()

        values = []
        for key, messages in groups.items():
            values.append(self.stat(messages))

        return list(groups.keys()), values
# -----
# Stats
# -----
def _count_messages(msg):
    return 1
count_messages = Stat(_count_messages, sum, "#messages")

def _count_words(msg):
    return msg.words_count
count_words = Stat(_count_words, sum, "#words")

def is_convo_start(msg):
    return 1 if msg.convo_start else 0
count_convo_starts = Stat(is_convo_start, sum, "#first texting")

def seq_occurency(seq):
    #This is a stat generator, not a stat
    def count_seq(msg):
        return msg.text.count(seq)
    return Stat(count_seq, sum, "Use of " +  seq)

# ta is short for timeline / author - these stats will be applied combined with the ta- group_by's
ta_stats = [count_messages, count_words, count_convo_starts] + [seq_occurency(seq) for seq in SEQUENCES]


# -----
# Grouping and plotting
# -----
class Aggregate():
    """
    Groups belong together with a way of plotting them
    """
    def __init__(self, group_by, plot, name):
        self.group_by = group_by
        self._plot = plot
        self.name = name

    def __call__(self, msg):
        return self.group_by(msg)

    def plot(self, stat_name, keys, values):
        self._plot(group=self.name, stat=stat_name, keys=keys, values=values)

# -----
# grouping methods
# -----
def _per_total(msg):
    return 0

def _per_day(msg):
    reference = messages[0]
    return (msg.send.date() - reference.send.date()).days

def _per_author(msg):
    return msg.author

def _per_hour(msg):
    return msg.send.hour 


# -----
# plotting
# -----
def actual_categorical_plot(group, stat, keys, values):
    name = stat + " " + group
    plt.clf()
    plt.bar(range(len(keys)), values)
    plt.xticks(range(len(keys)), keys)
    plt.title(name)
    plt.savefig("plots/" + name+".png")
    plt.clf()

def categorical_plot(group, stat, keys, values):
    name = stat + " " + group
    print(" ---- Results ----- \n", name)
    for key, value in zip(keys, values):
        print("   ", key, ":", value)
    if len(keys) > 1:
        actual_categorical_plot(group, stat, keys, values)

def per_hour_plot(group, stat, keys, values):
    perm = np.argsort(keys)
    actual_categorical_plot(group, stat, np.array(keys)[perm], np.array(values)[perm])


def smoothed(keys, values):
    svr = SVR(gamma=2)
    svr.fit(np.array(keys)[...,None], np.array(values)[...,None])
    return svr.predict(np.array(keys)[...,None])

def timeline_plot(group, stat, keys, values, fig=None):
    """
    If fig is None, plot in a new figure
    If fig is not None, use the group as label and plot in that figure
    """
    
    if fig is None:
        plt.clf()
        name = stat + " " + group
        plt.plot(keys, values)
        plt.title(name)
        plt.savefig("plots/" + name+".png")
        plt.clf()
    else:
        plt.plot(keys, values, label=group)



# -----
# Groups (combos from group_by and plots)
# -----
per_total   = Aggregate(_per_total, categorical_plot, "total")
per_day     = Aggregate(_per_day, timeline_plot, "per day")
per_author  = Aggregate(_per_author, categorical_plot, "per author")
per_hour    = Aggregate(_per_hour, per_hour_plot, "per hour")
ta_groups   = [per_total, per_day, per_author, per_hour]

for stat in ta_stats:
    analyzer = ApplyStat(messages, stat)
    for grouping in ta_groups:
        keys, values = analyzer.run(grouping)
        grouping.plot(stat.name, keys, values)

"""
Would be nice to combine group by's, to plot how many messages were sent each day
"""

class ComboGroup(Aggregate):
    def __init__(self,  time_group, cat_group):
        """
        main group decides the plot, should be the timeline
        Note that the arguments are different to Aggregate
        """
        self.time_group, self.cat_group = time_group, cat_group
        self.name = self.cat_group.name + " " + self.time_group.name

    def __call__(self, msg):
        return (self.cat_group(msg), self.time_group(msg))

    def plot(self, stat_name, keys, values):
        plt.clf()
        fig = plt.figure()

        cats = list(dict(keys).keys()) # keys are cat, time pairs
        for cat in cats:
            filtered_values = [value for key, value in zip(keys, values) if key[0]==cat]
            time_labels = [key[1] for key in keys if key[0]==cat]
            self.time_group._plot(cat, stat_name, time_labels, filtered_values, fig)

        plt.legend()
        plt.title(stat_name + " " + self.name)
        plt.savefig("plots/" + self.name+" "+stat_name+".png")
        plt.close('all')

time_author = ComboGroup(per_day, per_author)

per_author_per_day = ComboGroup(per_day, per_author)

for stat in ta_stats:
    analyzer = ApplyStat(messages, stat)
    keys, values = analyzer.run(per_author_per_day)
    per_author_per_day.plot(stat.name, keys, values)
