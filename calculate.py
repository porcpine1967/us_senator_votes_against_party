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
from time import sleep
import urllib2
from xml.dom.minidom import parse

# requires pyyaml
import yaml

LEGISLATORS_PICKLE = 'legislators.pickle'
ROLL_CALLS_PICKLE = 'roll_calls.pickle'
VERDICTS = { 'Yea': 'Y', 'Nay': 'N', 'Guilty': 'Y', 'Not Guilty': 'N' }

""" Current presidential candidates who were senators."""
CANDIDATE_IDS = (
    'S313', # Bernie Sanders
    'S370', # Cory A. Booker
    'S331', # Kirsten E. Gillibrand
    'S387', # Kamala D. Harris
    'S311', # Amy Klobuchar
    'S366', # Elizabeth Warren
    'S330', # Michael F. Bennet
    'S010', # Joseph Biden
)

""" Words used in the 'result' section of a roll call to indicate that the yeas won."""
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
    'Motion to Discharge Agreed to',
    'Motion to Proceed Agreed to',
    'Motion to Reconsider Agreed to',
    'Motion to Table Agreed to',
    'Motion to Table Motion to Recommit Agreed to',
    'Motion to Table Motion to Reconsider Agreed to',
    'Nomination Confirmed',
    'Point of Order Sustained',
    'Point of Order Well Taken',
    'Resolution Agreed to',
    'Resolution of Ratification Agreed to',
    'Veto Overridden',
)
""" Words used in the 'result' section of a roll call to indicate that the nays won. """
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

def load_senators(download):
    """ Builds new pickled senator data

    First, it downloads the data from github
    Second, it builds senators
    Third, it pickles them all in data/legislators/senators.pickle

    Parameters:
    download: try to download legislator data
    """
    if not os.path.isdir('data/legislators'):
        os.makedirs('data/legislators')

    if download:
        current_path = 'data/legislators/legislators-current.yaml'
        with open(current_path, 'wb') as f:
            for l in urllib2.urlopen('https://raw.githubusercontent.com/unitedstates/congress-legislators/master/legislators-current.yaml'):
                f.write(l)

        historical_path = 'data/legislators/legislators-historical.yaml'
        with open(historical_path, 'wb') as f:
            for l in urllib2.urlopen('https://github.com/unitedstates/congress-legislators/blob/master/legislators-historical.yaml?raw=true'):
                f.write(l)

    success = True
    senators = {}
    if os.path.exists(current_path):
        with open('data/legislators/legislators-current.yaml', 'rb') as f:
            senator_list = yaml.safe_load(f)
            for data in senator_list:
                try:
                    s = Senator(data, True)
                    senators[s.lis] = s
                except KeyError:
                    pass
    else:
        print 'No file at data/legislators/legislators-current.yaml. Please download from https://www.govtrack.us/data/congress-legislators/legislators-current.yaml'
        success = False

    if os.path.exists(historical_path):
        with open('data/legislators/legislators-historical.yaml', 'rb') as f:
            senator_list = yaml.safe_load(f)
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

    with open("data/legislators/{}".format(LEGISLATORS_PICKLE), 'wb') as f:
        pickle.dump(senators, f)

class SenatorLookup(object):
    """ Class for holding senator information."""
    def __init__(self):
        if not os.path.exists("data/legislators/{}".format(LEGISLATORS_PICKLE)):
            load_senators(False)
        with open("data/legislators/{}".format(LEGISLATORS_PICKLE), 'rb') as f:
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
        self.vote_cnt = 0
        self.betrayal_cnt = 0
        self.futile_cnt = 0

    @property
    def total_betrayal_pct(self):
        try:
            return self.total_betrayal_cnt / float(self.vote_cnt)
        except ZeroDivisionError:
            return 0.0

    @property
    def success_pct(self):
        try:
            return self.betrayal_cnt / float(self.total_betrayal_cnt)
        except ZeroDivisionError:
            return 0.0
    @property
    def total_betrayal_cnt(self):
        return self.betrayal_cnt + self.futile_cnt

    def _name_from_data(self, data):
        name_data = data['name']
        if 'official_full' in name_data:
            return name_data['official_full']
        else:
            return u'{} {}'.format(name_data['first'], name_data['last'])

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
        return '{} ({} - {})'.format(self.name, ','.join(self.parties), ','.join(self.states))

class UnknownResultError(ValueError):
    pass

def successful(result):
    """ Returns string indicating if yeas (Y) or nays (N) won a given roll call. """
    if result in SUCCESS_WORDS:
        return 'Y'
    if result in FAIL_WORDS:
        return 'N'
    if result == 'unknown':
        raise UnknownResultError('Result in other field. TODO: parse other field')
    raise ValueError('{} is not a documented result'.format(result))

class RollCallManager(object):
    """ Class for holding an array of roll_calls. """
    def __init__(self):
        self.roll_calls = []

def solo_node_value(doc, node_name):
    for node in doc.getElementsByTagName(node_name):
        return(text_value(node))
def text_value(node):
    for c in node.childNodes:
        return c.toxml()

class RollCall(object):
    """ Class for retaining information about the results of a roll call of votes in the Senate.

    Attributes:
    roll_call_id: the unique identifier of this roll call
    requires: the rule for the success of those in favor -- 1/2, 3/5, or 2/3
    votes: array containing all the votes by individual senators
    resolution: the detailed description of the result of the roll call
    success: 'Y' or 'N' -- indicatation by the resolution whether the yeas or nays won
    party_breakdown: dictionary of percentages of each party voting yea or nay, for
                     example, the keys would be Democrat-N, Democrat-Y, Republican-N, Republican-Y
                     for a roll call with senators in each category, and the total would add up to 2
                     (100% for each party)
    """

    def __init__(self, roll_call_data):
        self.roll_call_id = '{}{}{}'.format(solo_node_value(roll_call_data, 'congress'),
                                    solo_node_value(roll_call_data, 'session'),
                                    solo_node_value(roll_call_data, 'vote_number'))
        self.requires = solo_node_value(roll_call_data, 'majority_requirement')
        self.votes = self._load_votes(roll_call_data)
        self.resolution = solo_node_value(roll_call_data, 'vote_result')
        self.success = successful(self.resolution)
        self.party_breakdown = self._calculate_party_breakdown()
        self._set_betrayal_attributes_on_votes()

    def party_won(self, party):
        """ Whether the majority of votes by senators in the given party were
        on the side of success."""
        return self.party_breakdown['{}-{}'.format(party, self.success)] > .5

    def _load_votes(self, roll_call_data):
        """ Builds Vote objects to fill the votes array. Note, this only loads
        yeas and nays -- ignoring 'present' and 'not voting'."""
        return_data = []
        loaded = False
        for member in roll_call_data.getElementsByTagName('member'):
            vote = solo_node_value(member, 'vote_cast')
            if vote in VERDICTS.keys():
                loaded = True
                return_data.append(Vote(solo_node_value(member, 'lis_member_id'),
                                        solo_node_value(member, 'party'),
                                        VERDICTS[vote]))

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

    def _set_betrayal_attributes_on_votes(self):
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
        """ Whether the ultimate resolution of the roll call could have been accomplished
        by a single party without the assistance of members of the other. For example,
        consider a roll call that requires 1/2 is a success. If the yeas of one party
        on its own were greater than 50% of the roll call, then no betrayal would have been
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
    how many yeas would be necessary to carry the roll call. Assumes ties
    go to the nays for simplicity."""
    if requires == '1/2':
        return nays + 1
    elif requires == '2/3':
        return 2*nays + 1
    elif requires == '3/5':
        return 3*nays/2 + 1
    else:
        raise ValueError('Unknown success requirement: {}'.format(requires))

def necessary_nays(yeas, requires):
    """ Based on the number of yeas and the requirement for success,
    how many nays would be necessary to defeat the roll call. Assumes ties
    go to the nays for simplicity."""
    if requires == '1/2':
        return yeas
    elif requires == '2/3':
        return yeas/2
    elif requires == '3/5':
        return 2*yeas/3
    else:
        raise ValueError('Unknown success requirement: {}'.format(requires))

class Vote(object):
    """ Utility class for holding attributes of a given Senator's vote. """
    def __init__(self, senator_id, party, vote_answer):
        self.senator_id = senator_id
        self.party = party
        self.vote_answer = vote_answer
        self.betrayed_party = None
        self.futile_betrayal = None

SORT_KEYS = {
    'all': lambda x: x.vote_cnt,
    'total': lambda x: x.total_betrayal_cnt,
    'tot_pct': lambda x: x.total_betrayal_pct,
    'success': lambda x: x.betrayal_cnt,
    'fail': lambda x: x.futile_cnt,
    'pct': lambda x: x.success_pct,
}

def calculate_betrayal(vm, only_necessary = False, only_current = False, only_candidates = False, limit = 20, sort = 'pct'):
    sl = SenatorLookup()
    senators = set()
    for roll_call in vm.roll_calls:
        if only_necessary and not roll_call.betrayal_necessary:
            continue
        for vote in roll_call.votes:
            senator = sl.senators[vote.senator_id]
            senators.add(senator)
            senator.vote_cnt += 1
            if vote.betrayed_party:
                senator.betrayal_cnt += 1
            if vote.futile_betrayal:
                senator.futile_cnt += 1
    if only_necessary:
        print 'Only considering occasions in which neither party had enough votes to win'
    if only_current:
        print 'Only showing current senators'
    print 'Number of votes opposed to own party that subverted party desire, by senator'
    print '   All   Total  Pct Tot   Successful  Success Pct  Senator'

    print_cnt = 0

    for senator in sorted(senators, reverse=True, key=SORT_KEYS[sort]):
        if only_candidates and senator.lis not in CANDIDATE_IDS:
            continue
        if only_current and not senator.current:
            continue
        all_votes = senator.vote_cnt
        total = senator.total_betrayal_cnt
        betrayal_count = senator.betrayal_cnt
        success_pct = senator.success_pct
        print_cnt += 1
        print '{:>6} {:>6} {:>8.2f} {:>10} {:>12.2f}     {}'.format(all_votes, total, senator.total_betrayal_pct, betrayal_count, success_pct, str(senator))
        if limit > 0 and print_cnt >= limit:
            break

def resolution_hist(vm):
    """ Exploratory histogram """
    resolution_ctr = Counter()
    for roll_call in vm.roll_calls:
        resolution_ctr[roll_call.resolution] += 1
    print 'Resolutions count ordered by most common descending'
    for resolution, resolution_count in resolution_ctr.most_common():
        print resolution, resolution_count

def betrayal_hist(vm):
    """ Exploratory histogram """
    print 'Hist of number of betraying votes'
    betrayal_ctr = Counter()
    for roll_call in vm.roll_calls:
        betrayals = len([vote for vote in roll_call.votes if vote.betrayed_party])
        betrayal_ctr[betrayals] += 1
        if betrayals > 30:
            print roll_call.vote_id
    for betrayal_quantity, betrayal_quantity_occurences in betrayal_ctr.most_common():
        print betrayal_quantity, betrayal_quantity_occurences

def calculate_session(year):
    if int(year) < 1941:
        # before 1941, the divisions were not based on year
        print 'Unable to calculate session for years before 1941'
        sys.exit(1)
    # Sessions start in 1789 and last two years
    return (int(year) + 1)/2 - 894, (int(year) % 2) and 1 or 2

def load_year(year):
    """ Builds new pickled roll call data

    First, it rsyncs the json data from govtrack.us to data/{year}/
    Second, it builds the roll_calls
    Third, it pickles them all in data/{}/roll_calls.pickle
    """
    if int(year) < 1989:
        print 'This code does not work with data before 1989'
        sys.exit(1)

    session, subsession = calculate_session(year)
    try:
        os.makedirs('data/rollcalls/{}'.format(year))
    except OSError:
        pass
    opener = urllib2.build_opener()
    opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
    menu_path = 'data/rollcalls/{}/menu.xml'.format(year)
    if not os.path.exists(menu_path):
        print 'downloading', year
        url = 'https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_{}_{}.xml'.format(session, subsession)
        with open(menu_path, 'wb') as f:
            for l in opener.open(url):
                f.write(l)
    menu = parse(menu_path)
    for cnt, vote_number_node in enumerate(menu.getElementsByTagName('vote_number')):
        vote_number = text_value(vote_number_node)
        vote_number_path = 'data/rollcalls/{}/{}.xml'.format(year, vote_number)
        try:
            exists = os.stat(vote_number_path).st_size
        except OSError:
            exists = False
        if not exists:
            if not cnt % 3:
                sleep(2)
            url = 'https://www.senate.gov/legislative/LIS/roll_call_votes/vote{session}{subsession}/vote_{session}_{subsession}_{vote_number}.xml'.format(session=session, subsession=subsession, vote_number=vote_number)
            print 'downloading', url
            with open(vote_number_path, 'wb') as f:
                for l in opener.open(url):
                    f.write(l)
        
    roll_calls = []
    for root, dirs, files in os.walk("data/rollcalls/{}".format(year)):
        for filename in files:
            if filename == 'menu.xml':
                continue
            if filename.endswith('xml'):
                file_path = '{}/{}'.format(root, filename)
                with open(file_path, 'rb') as f:
                    try:
                        roll_calls.append(RollCall(parse(f)))
                    except:
                        print 'Error in {}'.format(file_path)
                        raise

    if roll_calls:
        with open("data/rollcalls/{}/{}".format(year, ROLL_CALLS_PICKLE), 'wb') as f:
            pickle.dump(roll_calls, f)
        return roll_calls
    else:
        print "Something wrong: no roll_calls for {}".format(year)
        sys.exit(1)

def year_iterator(args):
    if '-' in args.years:
        start, end = args.years.split('-')
        return xrange(int(start), int(end) + 1)
    else:
        return args.years.split(',')
    

def run(args):
    if args.action == 'load-senators':
        load_senators(True)
    elif args.action == 'load-years':
        for year in year_iterator(args):
            print 'Loading:', year
            load_year(year)
    else:
        vm = RollCallManager()
        for year in year_iterator(args):
            if os.path.exists("data/rollcalls/{}/{}".format(year, ROLL_CALLS_PICKLE)):
                with open("data/rollcalls/{}/{}".format(year, ROLL_CALLS_PICKLE), 'rb') as f:
                    roll_calls = pickle.load(f)
            else:
                roll_calls = load_year(year)
            vm.roll_calls.extend(roll_calls)
        calculate_betrayal(vm, args.only_necessary, args.only_current, args.only_pc, args.limit, args.sort)

if __name__ == '__main__':
    parser = ArgumentParser(description='Write out data about senators\' votes in opposition to the majority of their parties')
    parser.add_argument('years', type=str, help='csv (e.g. "1991,1992,1993" with no space) or simple range (e.g. "1991-2015") of years to parse')
    parser.add_argument('--action', type=str, default='calculate', help='Action to take: calculate, load-senators, load-year')
    parser.add_argument('--only-current', action='store_true', help='only show current senators')
    parser.add_argument('--only-necessary', action='store_true', help='limit betrayals to necessary ones')
    parser.add_argument('--limit', type=int, default=20, help='Number of senators to give data for')
    parser.add_argument('--only-pc', action='store_true', help='only show presidential candidates')
    parser.add_argument('--sort', type=str, default='pct', help='column to sort by: all, total, success, fail, pct')
    args = parser.parse_args()
    run(args)
