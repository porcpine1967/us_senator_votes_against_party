#!/usr/bin/env python
from argparse import ArgumentParser
from collections import Counter, defaultdict
import distutils.spawn
import json
import os
try:
   import cPickle as pickle
except:
   import pickle
import subprocess
import sys

# requires pyaml
import yaml

""" Words used in the 'result' section of a vote to indicate that the ayes won. """
SUCCESS_WORDS = (
    'Amendment Agreed to',
    'Amendment Germane',
    'Bill Passed',
    'Cloture Motion Agreed to',
    'Cloture on the Motion to Proceed Agreed to',
    'Concurrent Resolution Agreed to',
    'Conference Report Agreed to',
    'Decision of Chair Sustained',
    'Guilty',
    'Joint Resolution Passed',
    'Motion Agreed to',
    'Motion for Attendance Agreed to',
    'Motion to Adjourn Agreed to',
    'Motion to Proceed Agreed to',
    'Motion to Reconsider Agreed to',
    'Motion to Table Agreed to',
    'Motion to Table Motion to Recommit Agreed to',
    'Motion to Table Motion to Reconsider Agreed to',
    'Nomination Confirmed',
    'Point of Order Sustained',
    'Resolution Agreed to',
    'Resolution of Ratification Agreed to',
    'Veto Overridden',
)
""" Words used in the 'result' section of a vote to indicate that the nays won. """
FAIL_WORDS = (
    'Amendment Not Germane',
    'Amendment Rejected',
    'Bill Defeated',
    'Cloture Motion Rejected',
    'Cloture on the Motion to Proceed Rejected',
    'Concurrent Resolution Rejected',
    'Conference Report Rejected',
    'Decision of Chair Not Sustained',
    'Joint Resolution Defeated',
    'Motion Rejected',
    'Motion to Adjourn Rejected',
    'Motion to Discharge Rejected',
    'Motion to Postpone Rejected',
    'Motion to Proceed Rejected',
    'Motion to Recommit Rejected',
    'Motion to Refer Rejected',
    'Motion to Table Failed',
    'Nomination Rejected',
    'Not Guilty',
    'Objection Not Sustained',
    'Point of Order Not Sustained',
    'Point of Order Not Well Taken',
    'Resolution Rejected',
    'Resolution of Ratification Rejected',
    'Veto Sustained',
)

def load_senators(do_rsync):
    """ Builds new pickled senator data

    First, it rsyncs the legislator data from govtrack.us to data/legislators
    Second, it builds senators
    Third, it pickles them all in data/legislators/senators.pickle
    """
    if not os.path.isdir('data/legislators'):
        os.makedirs('data/legislators')
    if do_rsync and test_for_rsync():
        with open('/dev/null', 'wb') as f:
            if subprocess.call(['rsync', '-avz', '--delete', '--delete-excluded', '--exclude', '**/text-versions/', '--exclude', '*.xml', 'govtrack.us::govtrackdata/congress-legislators/legislators-current.yaml', 'data/legislators/legislators-current.yaml'], stdout=f, stderr=f):
                print """Rsync not working. Please download these two files and place them in data/legislators:
                         https://www.govtrack.us/data/congress-legislators/legislators-current.yaml
                         https://www.govtrack.us/data/congress-legislators/legislators-historical.yaml"""
            elif subprocess.call(['rsync', '-avz', '--delete', '--delete-excluded', '--exclude', '**/text-versions/', '--exclude', '*.xml', 'govtrack.us::govtrackdata/congress-legislators/legislators-historical.yaml', 'data/legislators/legislators-historical.yaml'], stdout=f, stderr=f):
                print """Rsync not working for historical legislators. Please download this file and place it in data/legislators:
                         https://www.govtrack.us/data/congress-legislators/legislators-historical.yaml"""
    elif do_rsync:
        print """No rsync, please download these two files and place them in data/legislators:
                 https://www.govtrack.us/data/congress-legislators/legislators-current.yaml
                 https://www.govtrack.us/data/congress-legislators/legislators-historical.yaml"""
    success = True
    senators = {}
    if os.path.exists('data/legislators/legislators-current.yaml'):
        with open('data/legislators/legislators-current.yaml', 'rb') as f:
            senator_list = yaml.load(f)
            for data in senator_list:
                try:
                    s = Senator(data, True)
                    senators[s.lis] = s
                except KeyError:
                    pass
    else:
        print 'No file at data/legislators/legislators-current.yaml. Please download from https://www.govtrack.us/data/congress-legislators/legislators-current.yaml'
        success = False

    if os.path.exists('data/legislators/legislators-historical.yaml'):
        with open('data/legislators/legislators-historical.yaml', 'rb') as f:
            senator_list = yaml.load(f)
            for data in senator_list:
                try:
                    s = Senator(data, False)
                    if s.lis in senators:
                        print "Data integrity issue: {} ({}) is in both current and historical records. Please update both legislators files".format(s.name, s.lis)
                        sys.exit(1)
                    senators[s.lis] = s
                except KeyError:
                    pass
    else:
        print 'No file at data/legislators/legislators-historical.yaml. Please download from https://www.govtrack.us/data/congress-legislators/legislators-historical.yaml'
        success = False

    if not success:
        sys.exit(1)

    with open('data/legislators/legislators.pickle', 'wb') as f:
        pickle.dump(senators, f)
def test_for_rsync():
    return bool(distutils.spawn.find_executable('rsync'))
    
class SenatorLookup(object):
    """ Class for loading senator information from a yaml file
    for later lookup. """
    def __init__(self):
        if not os.path.exists('data/legislators/legislators.pickle'):
            load_senators(False)
        with open('data/legislators/legislators.pickle', 'rb') as f:
            self.senators = pickle.load(f)
    def get_senator_info(self, lis):
        if lis in self.senators:
            return str(self.senators[lis])
        else:
            return str(lis)

class Senator(object):
    """ Utility class for holding information about a given Senator. """
    def __init__(self, data, current):
        self.lis = data['id']['lis']
        self.name = self._name_from_data(data)
        self.parties = self._parties_from_data(data)
        self.states = self._states_from_data(data)
        self.current = current

    def _name_from_data(self, data):
        name_data = data['name']
        if 'official_full' in name_data:
            return name_data['official_full']
        else:
            return '{} {}'.format(name_data['first'], name_data['last'])

    def _parties_from_data(self, data):
        parties = set()
        term_data = data['terms']
        for term in term_data:
            parties.add(term['party'])
        return parties

    def _states_from_data(self, data):
        states = set()
        term_data = data['terms']
        for term in term_data:
            states.add(term['state'])
        return states

    def __str__(self):
        return '{} {} - {}'.format(self.name, ','.join(self.parties), ','.join(self.states))

def successful(result):
    """ Returns string indicating if ayes (Y) or nays (N) won a given vote result. """
    if result in SUCCESS_WORDS:
        return 'Y'
    if result in FAIL_WORDS:
        return 'N'
    raise ValueError('{} is not a documented result'.format(result))

class VoteManager(object):
    """ Class for holding an array of votes. """
    def __init__(self):
        self.votes = []

class Vote(object):
    """ Class for retaining information about the results a vote in the Senate.
    Confusingly, it contains an array of 'votes', which are the individual indications
    of aye or nay by a given Senator.

    Attributes:
    vote_id: the unique identifier of this vote
    requires: the rule for the success of those in favor -- 1/2, 3/5, or 2/3
    votes: array containing all the votes of individual senators
    resolution: the string indicating the result of the vote
    success: 'Y' or 'N' indicating by the resolution whether the ayes or nays won
    party_breakdown: dictionary of percentages of each party voting aye or nay, for
    example, the keys would be Democrat-N, Democrat-Y, Republican-N, Republican-Y for
    a vote with senators in each category, and the total would add up to 2 (100% for each
    party)


    """
    def __init__(self, vote_data):
        self.vote_id = vote_data['vote_id']
        self.requires = vote_data['requires']
        self.votes = self._load_votes(vote_data)
        self.resolution = vote_data['result']
        self.success = successful(self.resolution)
        self.party_breakdown = self._calculate_party_breakdown()
        self._load_betrayed_party()

    def party_won(self, party):
        """ Whether the majority of votes by the party indicated by the parameter was
        on the side of success. """
        return self.party_breakdown['{}-{}'.format(party, self.success)] > .5

    def _load_votes(self, vote_data):
        """ Builds VoteResponse objects to fill the votes array. Note, this only loads
        ayes and nays -- ignoring 'present' and 'not voting'."""
        return_data = []
        v = vote_data['votes']
        loaded = False
        if 'Nay' in v:
            loaded = True
            for vr_data in v['Nay']:
                return_data.append(VoteResponse(vr_data['id'], vr_data['party'], 'N'))
        if 'Not Guilty' in v:
            loaded = True
            for vr_data in v['Not Guilty']:
                return_data.append(VoteResponse(vr_data['id'], vr_data['party'], 'N'))
        if 'Yea' in v:
            for vr_data in v['Yea']:
                if "VP" != vr_data:
                    return_data.append(VoteResponse(vr_data['id'], vr_data['party'], 'Y'))
        if 'Guilty' in v:
            for vr_data in v['Guilty']:
                return_data.append(VoteResponse(vr_data['id'], vr_data['party'], 'Y'))
        if not loaded:
            raise ValueError('Nothing to count')
        return return_data

    def _calculate_party_breakdown(self):
        breakdown_count = Counter()
        parties = set()
        for vr in self.votes:
            breakdown_count['{}-{}'.format(vr.party, vr.vote_answer)] += 1
            parties.add(vr.party)
        breakdown = {}
        for party in parties:
            party_yes = breakdown_count['{}-Y'.format(party)]
            party_no = breakdown_count['{}-N'.format(party)]
            party_total = float(party_yes + party_no)
            breakdown['{}-Y'.format(party)] = party_yes / party_total
            breakdown['{}-N'.format(party)] = party_no / party_total
        return breakdown

    def _load_betrayed_party(self):
        """ Sets the betrayed_party and futile_betrayal attributes of all
        VoteResponse objects in the votes array. """
        for vr in self.votes:
            party_won = self.party_won(vr.party)
            vr.betrayed_party = self.success == vr.vote_answer and not party_won
            vr.futile_betrayal = self.success != vr.vote_answer and party_won

    @property
    def yea_count(self):
        """ How many yeas. """
        return len([vr for vr in self.votes if vr.vote_answer == 'Y'])

    @property
    def nay_count(self):
        """ How many nays. """
        return len([vr for vr in self.votes if vr.vote_answer == 'N'])

    @property
    def betrayal_cnt(self):
        """ How many votes were against the majority of the voter's party. """
        return len([vr for vr in self.votes if vr.betrayed_party])

    @property
    def betrayal_necessary(self):
        """ Whether the ultimate resolution of the vote could have been accomplished
        by a single party without the assistance of members of the other. For example,
        in a 1/2 requires status and the vote was a success, if the ayes of one party
        on its own were greater than 50% of the vote, then no betrayal would have been
        necesssary. However, if the ayes of neither party on its own surpassed the 50%
        mark, then betrayal was necessary. """
        betrayals = self.betrayal_cnt
        if betrayals == 0:
            return False
        if self.success == 'Y':
            n_yeas = necessary_yeas(self.nay_count, self.requires)
            pct_n = (n_yeas - self.yea_count + betrayals)/float(betrayals)
        else:
            n_nays = necessary_nays(self.yea_count, self.requires)
            pct_n = (n_nays - self.nay_count + betrayals)/float(betrayals)
        return pct_n > 0


def necessary_yeas(nays, requires):
    """ Based on the number of nays and the requirement for success,
    how many yeas would be necessary to carry the vote. Assumes ties
    go to the nays for simplicity."""
    if requires == '1/2':
        return nays + 1
    elif requires == '2/3':
        return 2*nays + 1
    elif requires == '3/5':
        return 3*nays/2 + 1
    else:
        raise ValueError('Invalid requires: {}'.format(requires))

def necessary_nays(yeas, requires):
    """ Based on the number of ayes and the requirement for success,
    how many nays would be necessary to defeat the vote. Assumes ties
    go to the nays for simplicity. """
    if requires == '1/2':
        return yeas
    elif requires == '2/3':
        return yeas/2
    elif requires == '3/5':
        return 2*yeas/3
    else:
        raise ValueError('Invalid requires: {}'.format(requires))

class VoteResponse(object):
    """ Utility class for holding attributes of a given Senator's answer in a vote. """
    def __init__(self, senator_id, party, vote_answer):
        self.senator_id = senator_id
        self.party = party
        self.vote_answer = vote_answer
        self.betrayed_party = None
        self.futile_betrayal = None

def calculate_betrayal(vm, only_necessary = False, only_current = False, limit = 20):
    betrayal_ctr = Counter()
    futility_ctr = Counter()
    for vote in vm.votes:
        add_betrayal = not only_necessary or vote.betrayal_necessary
        for vr in vote.votes:
            if vr.betrayed_party and add_betrayal:
                betrayal_ctr[vr.senator_id] += 1
            if vr.futile_betrayal:
                futility_ctr[vr.senator_id] += 1
    print 'Number of votes opposed to own party that subverted party desire, by senator'
    print 'Betray  Success Pct  Senator'
    sl = SenatorLookup()

    print_cnt = 0
    for k, v in betrayal_ctr.most_common():
        if k in sl.senators:
            senator = sl.senators[k]
            if only_current and not senator.current:
                continue
            print_cnt += 1
            success_pct = float(v)/(v + futility_ctr[k])
            print '{:>7} {:>12.2f} {}'.format(v, success_pct, str(senator))
        if limit > 0 and print_cnt >= limit:
            break

def calculate_betrayal_pct(vm):
    senators = defaultdict(lambda:Counter())
    all_with_party = 0
    all_betray = 0
    for vote in vm.votes:
        for vr in vote.votes:
            senators[vr.senator_id][vr.betrayed_party] += 1
            if vr.betrayed_party:
                all_betray += 1
            else:
                all_with_party += 1
    sen_pcts = []
    for senator, ctr in senators.items():
        with_party = ctr[False]
        betray = ctr[True]
        total = with_party + betray
        sen_pcts.append((senator, float(betray) / total, total,))
    print 'Percent of votes opposed to own party that subverted party desire, by senator'
    for senator, pct, total in sorted(sen_pcts, key=lambda x: x[1]):
        print '{} {:.2f} {}'.format(senator, pct, total)
    print 'TOTAL: {}'.format(float(all_betray + all_with_party) / len(senators))
    print 'AVG: {:.2f}'.format(float(all_betray) / (all_betray + all_with_party))

def resolution_hist(vm):
    """ Exploratory histogram """
    resolution_ctr = Counter()
    for v in vm.votes:
        resolution_ctr[v.resolution] += 1
    print 'Resolutions count ordered by most common descending'
    for k, v in resolution_ctr.most_common():
        print k, v

def betrayal_hist(vm):
    """ Exploratory histogram """
    print 'Hist of number of betraying votes'
    betrayal_ctr = Counter()
    for vote in vm.votes:
        betrayals = len([vr for vr in vote.votes if vr.betrayed_party])
        betrayal_ctr[betrayals] += 1
        if betrayals > 30:
            print vote.vote_id
    for k, v in betrayal_ctr.most_common():
        print k, v

def win_with_betrayal(vm):
    """ Exploratory histogram """
    print 'Hist of percentage of betrayals necessary for win'
    pct_necessary_betrayal_ctr = Counter()
    no_betrayal_ctr = 0
    for vote in vm.votes:
        betrayals = vote.betrayal_cnt
        if betrayals == 0:
            no_betrayal_ctr += 1
            continue
        if vote.success == 'Y':
            n_yeas = necessary_yeas(vote.nay_count, vote.requires)
            pct_n = (n_yeas - vote.yea_count + betrayals)/float(betrayals)
        else:
            nnays = necessary_nays(vote.yea_count, vote.requires)
            pct_n = (nnays - vote.nay_count + betrayals)/float(betrayals)
        if pct_n <= 0:
            key = '0.0'
        else:# pct_n > 1:
            key = '1.0'
        # else:
        #     key = '{:.1f}'.format(pct_n)
        pct_necessary_betrayal_ctr[key] += 1
    print 'nob', no_betrayal_ctr
    for k in sorted(pct_necessary_betrayal_ctr.keys()):
        print k, pct_necessary_betrayal_ctr[k]

def conscience(vm):
    """ A negative vote when both parties are in favor.

    Does not consider opposition by Independent as negating."""
    for vote in vm.votes:
        if vote.success != 'Y':
            continue
        favor_cnt = 0
        for k, v in vote.party_breakdown.items():
            pass



def run(args):
    if args.action == 'load-senators':
        # load_senators(False)
        sl = SenatorLookup()
    else:
        vm = VoteManager()
        for dirname in args.dirs.split(','):
            for root, dirs, files in os.walk(dirname):
                for f in files:
                    if f.endswith('json'):
                        file_path = '{}/{}'.format(root, f)
                        with open(file_path, 'rb') as jfile:
                            vm.votes.append(Vote(json.load(jfile)))

        calculate_betrayal(vm, args.only_necessary, args.only_current, args.limit)

if __name__ == '__main__':
    parser = ArgumentParser(description='Write out data about senator\'s betrayals')
    parser.add_argument('dirs', type=str, help='csv of years to parse')
    parser.add_argument('--action', type=str, default='calculate', help='Action to take: calculate, load-senators, load-year')
    parser.add_argument('--only-current', action='store_true', help='limit to current senators')
    parser.add_argument('--only-necessary', action='store_true', help='limit betrayals to necessary ones')
    parser.add_argument('--limit', type=int, default=20, help='Number of senators to give data for')
    args = parser.parse_args()
    run(args)
