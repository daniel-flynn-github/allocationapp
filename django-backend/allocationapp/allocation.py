import networkx as nx
import random
import math
import itertools

from allocationapp.models import Preference

def increase_preference_weight_for_previous_team_to_discourage(graduates):
    for grad in graduates:
        if grad.assigned_team != None:
            preference = Preference.objects.get_or_create(grad=grad, team=grad.assigned_team)
            preference[0].weight += 100 #indexed at 0 because get_or_create returns a tuple (object, bool)
            preference[0].save()

# function using networkx library to run a min_cost_max_flow
# with_lower_bound attribute is False by default, if true the algorithm is run capping the team capacities at the lower bound
def run_min_cost_max_flow(graduates, teams, with_lower_bound=False):
    G = nx.DiGraph()

    # each graduate is a node in the network
    for grad in graduates:
        G.add_node(grad, demand=-1)

    # each team is a node in the network
    if (with_lower_bound):
        for team in teams:
            G.add_node(team, demand=team.lower_bound)
    else:
        # teams will be a dictionary only if run_min_cost_max_flow is run on the second run of an allocation with a lower bound with more vacancies than graduates
        if type(teams) == dict:
            for team,capacity in teams.items():
                G.add_node(team, demand=capacity)
        else:
            for team in teams:
                G.add_node(team, demand=team.capacity)

    for grad in graduates:
        for team in teams:
            # 6 - to revert the scale from 1 to 5
            if (Preference.objects.get(grad=grad, team=team).weight >= 100):
                G.add_edge(grad, team, weight=Preference.objects.get(grad=grad, team=team).weight)
            else:
                # 6 - to revert the scale from 1 to 5
                G.add_edge(grad, team, weight = 6 - (Preference.objects.get(grad=grad, team=team).weight))

    flowDict = nx.min_cost_flow(G)

    return flowDict

def run_allocation(allGraduates, allTeams, testing=False):
    increase_preference_weight_for_previous_team_to_discourage(allGraduates)
    total_vacancies = 0
    vacancies_on_lower_bound = 0
    for team in allTeams:
        total_vacancies += team.capacity
        vacancies_on_lower_bound += team.lower_bound

    if len(allGraduates) > total_vacancies:
        print("Error: not enough spaces for graduates")
        exit()

    if len(allGraduates) < vacancies_on_lower_bound:
        print("Error: not enough grads to satisfy lower bound")
        exit()

    # alg run only once when total vacancies equal the amount of graduates
    if len(allGraduates) == total_vacancies:
        first_run_allocation = run_min_cost_max_flow(allGraduates,allTeams)
        allocation_result = {team:[] for team in allTeams}
        # assign teams to each graduate
        for grad in first_run_allocation:
            for team in first_run_allocation[grad]:
                if(first_run_allocation[grad][team] == 1):
                    grad.assigned_team = team
                    grad.save()
                    allocation_result[team].append(grad)
    # alg will need to be run twice when there are more vacancies than graduates
    elif len(allGraduates) >= vacancies_on_lower_bound:
        # randomly shuffle graduates to randomise who gets picked for first or second run
        # (since first-run people are more likely to get their preferred team)
        if (not testing):
            random.shuffle(allGraduates)
        randomly_sampled_grads_for_first_run = allGraduates[:vacancies_on_lower_bound]
        randomly_sampled_grads_for_second_run = allGraduates[vacancies_on_lower_bound:]
        # alg first run
        first_run_allocation = run_min_cost_max_flow(randomly_sampled_grads_for_first_run, allTeams, with_lower_bound=True)
        remaining_spaces = total_vacancies - vacancies_on_lower_bound
        # modify team capacity based on graduates left and remaining spaces in the team (becuase they need to be equal)
        remaining_teams = {}
        integers = []
        fractions = {}
        for team in allTeams:
            frac,whole = math.modf((team.capacity-team.lower_bound)*(len(randomly_sampled_grads_for_second_run)/remaining_spaces))
            remaining_teams[team] = int(whole)
            integers.append(whole)
            fractions[team] = frac
        needed = len(randomly_sampled_grads_for_second_run) - sum(integers)
        fractions = {k: v for k, v in sorted(fractions.items(), key=lambda item: item[1])[::-1]}
        for k,v in dict(itertools.islice(fractions.items(), int(needed))).items():
            remaining_teams[k] += 1
        # alg second run
        second_run_allocation = run_min_cost_max_flow(randomly_sampled_grads_for_second_run,remaining_teams)

        allocation_result = {team:[] for team in allTeams}
        # assign teams to each graduate
        for grad in first_run_allocation:
            for team in first_run_allocation[grad]:
                if(first_run_allocation[grad][team] == 1):
                    grad.assigned_team = team
                    grad.save()
                    allocation_result[team].append(grad)
        for grad in second_run_allocation:
            for team in second_run_allocation[grad]:
                if(second_run_allocation[grad][team] == 1):
                    grad.assigned_team = team
                    grad.save()
                    allocation_result[team].append(grad)
        print(allocation_result)