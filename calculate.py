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

""" Words used in the 'result' section of a tally to indicate that the yeas won. """
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
""" Words used in the 'result' section of a tally to indicate that the nays won. """
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
    'Motion to Reconsider Rejected',
    'Motion to Table Failed',
    'Motion to Table Motion to Reconsider Rejected',
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

class UnknownResultError(ValueError):
    pass

def successful(result):
    """ Returns string indicating if yeas (Y) or nays (N) won a given tally. """
    if result in SUCCESS_WORDS:
        return 'Y'
    if result in FAIL_WORDS:
        return 'N'
    if result == 'unknown':
        raise UnknownResultError()
    raise ValueError('{} is not a documented result'.format(result))

class TallyManager(object):
    """ Class for holding an array of tallies. """
    def __init__(self):
        self.tallies = []

class Tally(object):
    """ Class for retaining information about the results of a call for votes (called "tally") in the Senate.

    Attributes:
    tally_id: the unique identifier of this tally
    requires: the rule for the success of those in favor -- 1/2, 3/5, or 2/3
    votes: array containing all the votes by individual senators
    resolution: the string indicating the result of the tally
    success: 'Y' or 'N' indicating by the resolution whether the yeas or nays won
    party_breakdown: dictionary of percentages of each party voting yea or nay, for
    example, the keys would be Democrat-N, Democrat-Y, Republican-N, Republican-Y for
    a tally with senators in each category, and the total would add up to 2 (100% for each
    party)
    """

    def __init__(self, tally_data):
        self.tally_id = tally_data['vote_id']
        self.requires = tally_data['requires']
        self.votes = self._load_votes(tally_data)
        self.resolution = tally_data['result']
        self.success = successful(self.resolution)
        self.party_breakdown = self._calculate_party_breakdown()
        self._load_betrayed_party()

    def party_won(self, party):
        """ Whether the majority of votes by senators in the given party were
        on the side of success."""
        return self.party_breakdown['{}-{}'.format(party, self.success)] > .5

    def _load_votes(self, tally_data):
        """ Builds Vote objects to fill the votes array. Note, this only loads
        yeas and nays -- ignoring 'present' and 'not voting'."""
        return_data = []
        votes = tally_data['votes']
        loaded = False
        if 'Nay' in votes:
            loaded = True
            for vote_data in votes['Nay']:
                return_data.append(Vote(vote_data['id'], vote_data['party'], 'N'))
        if 'Not Guilty' in votes:
            loaded = True
            for vote_data in votes['Not Guilty']:
                return_data.append(Vote(vote_data['id'], vote_data['party'], 'N'))
        if 'Yea' in votes:
            loaded = True
            for vote_data in votes['Yea']:
                if "VP" != vote_data:
                    return_data.append(Vote(vote_data['id'], vote_data['party'], 'Y'))
        if 'Guilty' in votes:
            loaded = True
            for vote_data in votes['Guilty']:
                return_data.append(Vote(vote_data['id'], vote_data['party'], 'Y'))
        if not loaded:
            raise ValueError('Nothing useful to count')
        return return_data

    def _calculate_party_breakdown(self):
        """ Generates a dictionary with party_name-vote keys and the percentage
        of the senators in the party who voted yea or nay (ignoring senators
        who did not vote yea or nay for calculating percentage)."""
        breakdown_count = Counter()
        parties = set()
        for vote in self.votes:
            breakdown_count['{}-{}'.format(vote.party, vote.vote_answer)] += 1
            parties.add(vote.party)
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
        Vote objects in the votes array. """
        for vote in self.votes:
            party_won = self.party_won(vote.party)
            vote.betrayed_party = self.success == vote.vote_answer and not party_won
            vote.futile_betrayal = self.success != vote.vote_answer and party_won

    @property
    def yea_count(self):
        """ How many yeas. """
        return len([vote for vote in self.votes if vote.vote_answer == 'Y'])

    @property
    def nay_count(self):
        """ How many nays. """
        return len([vote for vote in self.votes if vote.vote_answer == 'N'])

    @property
    def betrayal_cnt(self):
        """ How many votes were against the majority of the voter's party. """
        return len([vote for vote in self.votes if vote.betrayed_party])

    @property
    def betrayal_necessary(self):
        """ Whether the ultimate resolution of the tally could have been accomplished
        by a single party without the assistance of members of the other. For example,
        consider a tally that requires 1/2 is a success. If the yeas of one party
        on its own were greater than 50% of the tally, then no betrayal would have been
        necesssary. However, if the yeas of neither party on its own surpassed the 50%
        mark, then betrayal was necessary."""
        betrayals = self.betrayal_cnt
        if self.betrayal_cnt == 0:
            return False
        if self.success == 'Y':
            number_yeas_needed = necessary_yeas(self.nay_count, self.requires)
            number_non_betrayals = self.yea_count - self.betrayal_cnt
            return number_yeas_needed > number_non_betrayals
        else:
            number_nays_needed = necessary_nays(self.yea_count, self.requires)
            number_non_betrayals = self.nay_count - self.betrayal_cnt
            return number_nays_needed > number_non_betrayals


def necessary_yeas(nays, requires):
    """ Based on the number of nays and the requirement for success,
    how many yeas would be necessary to carry the tally. Assumes ties
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
    """ Based on the number of yeas and the requirement for success,
    how many nays would be necessary to defeat the tally. Assumes ties
    go to the nays for simplicity."""
    if requires == '1/2':
        return yeas
    elif requires == '2/3':
        return yeas/2
    elif requires == '3/5':
        return 2*yeas/3
    else:
        raise ValueError('Invalid requires: {}'.format(requires))

class Vote(object):
    """ Utility class for holding attributes of a given Senator's vote. """
    def __init__(self, senator_id, party, vote_answer):
        self.senator_id = senator_id
        self.party = party
        self.vote_answer = vote_answer
        self.betrayed_party = None
        self.futile_betrayal = None

def calculate_betrayal(vm, only_necessary = False, only_current = False, limit = 20):
    betrayal_ctr = Counter()
    futility_ctr = Counter()
    for tally in vm.tallies:
        add_betrayal = not only_necessary or tally.betrayal_necessary
        for vote in tally.votes:
            if vote.betrayed_party and add_betrayal:
                betrayal_ctr[vote.senator_id] += 1
            if vote.futile_betrayal:
                futility_ctr[vote.senator_id] += 1
    print 'Number of votes opposed to own party that subverted party desire, by senator'
    print 'Betray  Success Pct  Senator'
    sl = SenatorLookup()

    print_cnt = 0
    for senator_id, betrayal_count in betrayal_ctr.most_common():
        if senator_id in sl.senators:
            senator = sl.senators[senator_id]
            if only_current and not senator.current:
                continue
            print_cnt += 1
            success_pct = float(betrayal_count)/(betrayal_count + futility_ctr[senator_id])
            print '{:>7} {:>12.2f} {}'.format(betrayal_count, success_pct, str(senator))
        if limit > 0 and print_cnt >= limit:
            break

def resolution_hist(vm):
    """ Exploratory histogram """
    resolution_ctr = Counter()
    for tally in vm.tallies:
        resolution_ctr[tally.resolution] += 1
    print 'Resolutions count ordered by most common descending'
    for resolution, resolution_count in resolution_ctr.most_common():
        print resolution, resolution_count

def betrayal_hist(vm):
    """ Exploratory histogram """
    print 'Hist of number of betraying votes'
    betrayal_ctr = Counter()
    for tally in vm.tallies:
        betrayals = len([vote for vote in tally.votes if vote.betrayed_party])
        betrayal_ctr[betrayals] += 1
        if betrayals > 30:
            print tally.vote_id
    for betrayal_quantity, betrayal_quantity_occurences in betrayal_ctr.most_common():
        print betrayal_quantity, betrayal_quantity_occurences

def calculate_session(year):
    if int(year) < 1941:
        print 'Unable to calculate session for years before 1941'
        sys.exit(1)
    if int(year) < 1991:
        print 'WARNING: years before 1991 have not been tested'
    # Sessions start in 1789 and last two years
    return (int(year) + 1)/2 - 894

def load_year(year):
    session = calculate_session(year)
    if test_for_rsync():
        if not os.path.isdir('data'):
            os.makedirs('data')
        with open('/dev/null', 'wb') as f:
            if subprocess.call(['rsync', '-avz', '--delete', '--delete-excluded', '--exclude', '**/text-versions/', '--exclude', '*.xml', 'govtrack.us::govtrackdata/congress/{}/votes/{}/s*'.format(session, year), 'data/{}'.format(year)], stdout=f, stderr=f):
                print "Rsync not working for {year}. Please download all json in subdirectories of https://www.govtrack.us/data/congress/{session}/votes/{year}/s*".format(year=year, session=session)
    else:
        print "Rsync not working for {year}. Please download all json in subdirectories of https://www.govtrack.us/data/congress/{session}/votes/{year}/s*".format(year=year, session=session)

    tallies = []
    for root, dirs, files in os.walk("data/{}".format(year)):
        for filename in files:
            if filename.endswith('json'):
                file_path = '{}/{}'.format(root, filename)
                with open(file_path, 'rb') as f:
                    try:
                        tallies.append(Tally(json.load(f)))
                    except:
                        print 'Error in {}'.format(file_path)
                        raise

    if tallies:
        with open("data/{}/tallies.pickle".format(year), 'wb') as f:
            pickle.dump(tallies, f)
        return tallies
    else:
        print "Something wrong: no tallies for {}".format(year)
        sys.exit(1)

def run(args):
    if args.action == 'load-senators':
        load_senators(True)
    elif args.action == 'load-years':
        for year in args.years.split(','):
            print 'Loading:', year
            load_year(year)
    else:
        vm = TallyManager()
        for year in args.years.split(','):
            if os.path.exists("data/{}/tallies.pickle".format(year)):
                with open("data/{}/tallies.pickle".format(year), 'rb') as f:
                    tallies = pickle.load(f)
            else:
                tallies = load_year(year)
            vm.tallies.extend(tallies)
        calculate_betrayal(vm, args.only_necessary, args.only_current, args.limit)

if __name__ == '__main__':
    parser = ArgumentParser(description='Write out data about senator\'s betrayals')
    parser.add_argument('years', type=str, help='csv of years to parse')
    parser.add_argument('--action', type=str, default='calculate', help='Action to take: calculate, load-senators, load-year')
    parser.add_argument('--only-current', action='store_true', help='limit to current senators')
    parser.add_argument('--only-necessary', action='store_true', help='limit betrayals to necessary ones')
    parser.add_argument('--limit', type=int, default=20, help='Number of senators to give data for')
    args = parser.parse_args()
    run(args)
