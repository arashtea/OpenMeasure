import numpy as np
import os
import sys
import math
curr_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(curr_dir + '/module/script')

import cvxpySolver
from observeMatrix import observeMatrix
import performanceMetric

from OpenMeasure import OpenMeasure


class TMEwLB(OpenMeasure):
	def __init__(self, tmfile, sw_route_file, flow_route_file, prefix_file, SDNSwitchList, Tao):
		OpenMeasure.__init__(self, tmfile, sw_route_file, flow_route_file, prefix_file, SDNSwitchList, Tao)
		OpenMeasure.loadFile(self)
		OpenMeasure.popSNMPLinkLoad(self)
		self.swKj = {}
		self.cstr = 'SNMP + RE + ideal prediction'

	
	def set_swKj(self, sw_Kj):
		self.swKj = sw_Kj
		Kj = sum([self.swKj[sw] for sw in self.swKj])
		self.cstr += ', K={0}'.format(Kj)


	def set_rulePlacementAlgo(self, algo):
		self.method = algo
		self.cstr += ', {0}'.format(algo)
 

	def TMEwLB(self):
		### populate OF switch routing entries
		swHj = self.OM.SDNSwitchRoutingEntries_multi()
		for sw in swHj:
			print "OF Switch {0} has routing entries {1}".format(sw, len(swHj[sw]))
	
		### static aggregation: MLRF
		swHj = self.OM.MLRF_multi(self.swKj)
		for sw in swHj:
			print "OF Switch {0} has entries (RE+ME) {1}".format(sw, len(swHj[sw]))		

		### construct network-wide observation matrix
		D = self.OM.setupOM()

	        traffic_estm = []
        	for fl in range(self.N):
                	traffic_estm.append([])
		
		t_epoch = 0
		# MLRF to boot-strap online learning algorithms
		col_epoch = [[row[t_epoch]] for row in self.tmTrue[0:self.N]]
		Y = np.mat(D) * np.mat(col_epoch)
		Y = np.array(Y.tolist())
		
		W = np.ones([1, self.N])
		x_epoch = cvxpySolver.estm_TM(Y, D, W, self.N)
		x_epoch = [round(k) for k in x_epoch]
		
		for fl in range(self.N):
			traffic_estm[fl].append(x_epoch[fl])

		t_epoch += 1
		""" Debug """
		hitRate = 0
		
        	while( t_epoch < self.Tc):
			col_epoch = [row[t_epoch] for row in self.tmTrue[0:self.N]]
			index = sorted(range(len(col_epoch)), key = lambda k: col_epoch[k], reverse=True)
			
			# rule placement
			if self.method == "LastHop": 
				[sw_bj, D] = self.OM.LastHop(index, self.swKj, False)
			elif self.method == "Greedy":
				[sw_bj, D] = self.OM.Greedy(index, self.swKj, False)
			elif self.method == "ILP":
				[sw_bj, D] = self.OM.ILP(col_epoch, self.swKj)

			# calculate large flows hitRate
			measured = []
			for sw in sw_bj:
				for fl in sw_bj[sw]:
					measured.append(fl)

			K = len(measured)
			match = sum([1 for fl in measured if fl in index[0:K]])				
			hitRate += match / float(K)

        	        ### estimate TM
			col_epoch = [[row[t_epoch]] for row in self.tmTrue[0:self.N]]
        	        Y = np.mat(D) * np.mat(col_epoch)
        	        Y = np.array(Y.tolist())

        	        W = np.ones([1, self.N])
        	        x_epoch = cvxpySolver.estm_TM(Y, D, W, self.N)
        	        x_epoch = [round(k) for k in x_epoch]

        	        for fl in range(self.N):
                	        traffic_estm[fl].append(x_epoch[fl])
	
        	        ### ok, we just finished one t_epoch and move to next
                	t_epoch += 1

     		""" Debug """
        	print "number of flows in tmEstm: ", len(traffic_estm)
        	print "number of time intervals in tmEstm: ", len(traffic_estm[0])
		self.tmEstm = traffic_estm
		hitRate /= float(self.Tc - 1)

		### evaluate performance metric
		PM = performanceMetric.perfMetric(self.tmTrue, self.tmEstm, self.IPPrefix)
		result = PM.calMetrics()
		result.append(hitRate)
		return result


if __name__ == "__main__":
	pass
