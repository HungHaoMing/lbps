import copy
import re
from viewer import msg_fail, msg_warning, M3_result
from math import ceil
from config import ONE_HOP_TDD_CONFIG, TWO_HOP_TDD_CONFIG
from pprint import pprint

"""[summary] internal support function

[description]
1. isBackhaulResult: check if a list of device name is belong to backhaul link
2. mergeList: in M3 mapping, for update the final result [pass by reference]

"""

def isBackhaulResult(devices):
	pre = "isBackhaulResult\t"

	if not devices:
		# msg_warning("input value is an empty list", pre=pre)
		return

	if type(devices) is list:
		devices = [item for sublist in devices for item in sublist] if type(devices[0]) is list else devices
		check = list(map(lambda x: re.search('UE*', x), devices))
		return True if not any(check) else False

	else:
		msg_fail("input type should be a list of device name", pre=pre)

def filterByInterface(schedule_result, map_result, interface):
	pre = "filterByInterface\t"

	try:
		check = list(map(lambda x: isBackhaulResult(x), schedule_result))

		for i in range(len(schedule_result)):

			if interface == 'backhaul':
				map_result[i] = map_result[i] if check[i] else []
			else:
				map_result[i] = map_result[i] if not check[i] else []

	except Exception as e:
		msg_fail(str(e), pre=pre)

def mergeList(target, resource):
	pre = "mergeList\t\t"

	try:

		# init
		if not target and len(resource) > len(target):
			target = resource

		elif len(target) == len(resource):
			for i in range(len(resource)):
				target[i].append(resource[i]) if resource[i] else target[i]

		return target

	except Exception as e:
		msg_fail(str(e), pre=pre)

"""[summary] external function

[description]
1. one_to_one_first_mapping: M3 mapping back to real timeline

"""

def one_to_one_first_mapping(TDD_config):

	pre = "mapping::M3\t\t"

	try:
		v_timeline = [0 for i in range(10)]

		RSC = 10
		VSC = TDD_config.count('D')*RSC/len(v_timeline)
		v_timeline = [{'TTI':[], 'VSC':VSC} for i in range(len(v_timeline))]
		track_index = 0

		for i in range(len(TDD_config)):
			TDD_config[i] = {'TTI':i+1, 'RSC':RSC} if TDD_config[i] is 'D' else 0
		TDD_config = [i for i in TDD_config if type(i) is dict]

		# mapping
		for i in range(len(v_timeline)):

			if TDD_config[track_index]['RSC'] >= v_timeline[i]['VSC']:
				v_timeline[i]['TTI'].append(TDD_config[track_index]['TTI'])
				TDD_config[track_index]['RSC'] -= v_timeline[i]['VSC']
				v_timeline[i]['VSC'] = 0
				track_index = (track_index+1)%len(TDD_config)
				continue

			for j in [(track_index+t)%len(TDD_config) for t in range(len(TDD_config))]:
				if v_timeline[i]['VSC'] == 0:
					break
				if TDD_config[j]['RSC'] == 0:
					continue

				v_timeline[i]['TTI'].append(TDD_config[j]['TTI'])

				if TDD_config[j]['RSC']<=v_timeline[i]['VSC']:
					v_timeline[i]['VSC'] -= TDD_config[j]['RSC']
					TDD_config[j]['RSC'] = 0
				else :
					TDD_config[j]['RSC'] -= v_timeline[i]['VSC']
					v_timeline[i]['VSC'] =0

			track_index = (track_index+1)%len(TDD_config)

		return [i['TTI'] for i in v_timeline]

	except Exception as e:
		msg_fail(str(e), pre=pre)

def one_to_one_first_mapping_2hop(device, interface, schedule_result):

	pre = "mapping::M3_2hop\t"

	try:
		status = device.link[interface][0].status
		TDD_config = device.tdd_config
		backhaul_subframe = []
		tracking_RN = 0
		result = []

		while tracking_RN != len(device.childs):

			# two hop: backhaul then access
			if interface == 'backhaul':
				RSC = device.capacity[interface]
				VSC = device.virtualCapacity[interface]
				TDD_config = device.tdd_config

			# one hop: access
			else:
				relay = device.childs[tracking_RN]
				RSC = relay.capacity[interface]
				VSC = relay.virtualCapacity[interface]
				TDD_config = relay.tdd_config

			real_subframe = TDD_config*(ceil(len(schedule_result)/len(TDD_config)))
			real_subframe = real_subframe[:len(schedule_result)]
			real_timeline = [[] for i in range(len(real_subframe))]
			real_timeline_RSC = {i:RSC for i in range(len(real_subframe)) \
								if real_subframe[i] is status and i not in backhaul_subframe}
			tracking_list = list(sorted(real_timeline_RSC.keys()))
			tracking_index = 0

			# mapping
			for i in range(len(schedule_result)):
				if real_timeline_RSC[tracking_list[tracking_index]] >= VSC:
					real_timeline[i].append(tracking_list[tracking_index])
					real_timeline_RSC[tracking_list[tracking_index]] -= VSC
					tracking_index = (tracking_index+1)%len(tracking_list)
					continue
				else:
					tmp = copy.deepcopy(VSC)

					while any(real_timeline_RSC[i] is not 0 for i in tracking_list) and tmp >0:
						real_timeline[i].append(tracking_list[tracking_index])
						tmp -= real_timeline_RSC[tracking_list[tracking_index]]
						real_timeline_RSC[tracking_list[tracking_index]] = 0
						tracking_index = (tracking_index+1)%len(tracking_list)
					if tmp > 0:
						msg_warning("needs more %g bits capacity" % tmp, pre=pre)

			filterByInterface(schedule_result, real_timeline, interface)
			result = mergeList(result, real_timeline)

			# filter
			for i in range(len(result)):
				result[i] = result[i] if schedule_result[i] else []

			if interface == 'backhaul':
				backhaul_subframe = [item for sublist in real_timeline for item in sublist]

			tracking_RN = tracking_RN+1 if interface == 'access' else 0
			interface = 'access'

		return result

	except Exception as e:
		msg_fail(str(e), pre=pre)