"""
ATIK AI - Route Optimizer
OR-Tools ile rota ve atama optimizasyonu
"""
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
import numpy as np

from ..core.exceptions import AtikAIError

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Optimizasyon sonucu"""
    total_cost: float
    total_distance: float
    assignments: List[Dict]     # [{source_id, receiver_id, waste_id, quantity, cost}]
    routes: List[List[int]] = field(default_factory=list)  # VRP çözümü için
    solver_status: str = "optimal"
    solve_time_ms: float = 0
    
    @property
    def num_assignments(self) -> int:
        return len(self.assignments)
    
    def to_dict(self) -> dict:
        return {
            "total_cost": self.total_cost,
            "total_distance": self.total_distance,
            "num_assignments": self.num_assignments,
            "assignments": self.assignments,
            "routes": self.routes,
            "solver_status": self.solver_status,
            "solve_time_ms": self.solve_time_ms
        }


class RouteOptimizer:
    """
    Rota ve Atama Optimizasyonu
    
    OR-Tools kullanarak:
    - Atık-Tesis atama optimizasyonu
    - Vehicle Routing Problem (VRP)
    - Transport maliyeti minimizasyonu
    """
    
    def __init__(self, time_limit_seconds: int = 30):
        self.time_limit = time_limit_seconds
        self._ortools_available = None
    
    @property
    def ortools_available(self) -> bool:
        """OR-Tools yüklü mü?"""
        if self._ortools_available is None:
            try:
                from ortools.linear_solver import pywraplp
                from ortools.constraint_solver import routing_enums_pb2
                from ortools.constraint_solver import pywrapcp
                self._ortools_available = True
            except ImportError:
                self._ortools_available = False
                logger.warning("OR-Tools yüklü değil. pip install ortools")
        return self._ortools_available
    
    # =========================================================================
    # ATAMA OPTİMİZASYONU
    # =========================================================================
    
    def optimize_assignment(
        self,
        sources: List[Dict],      # [{id, capacity, coords, cost_per_ton}]
        receivers: List[Dict],    # [{id, demand, coords, max_price}]
        cost_matrix: np.ndarray,  # Transport cost matrix [sources x receivers]
    ) -> OptimizationResult:
        """
        Atık-Tesis atama optimizasyonu
        
        Minimize: Toplam nakliye maliyeti
        Subject to:
        - Her alıcının talebi karşılansın
        - Her kaynağın kapasitesi aşılmasın
        """
        if not self.ortools_available:
            return self._greedy_assignment(sources, receivers, cost_matrix)
        
        from ortools.linear_solver import pywraplp
        import time
        
        start_time = time.time()
        
        n_sources = len(sources)
        n_receivers = len(receivers)
        
        # Solver
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            solver = pywraplp.Solver.CreateSolver('GLOP')
        
        # Karar değişkenleri: x[i][j] = kaynak i'den alıcı j'ye gönderilen miktar
        x = {}
        for i in range(n_sources):
            for j in range(n_receivers):
                x[i, j] = solver.NumVar(0, solver.infinity(), f'x_{i}_{j}')
        
        # Kısıtlar
        # 1. Kaynak kapasitesi
        for i in range(n_sources):
            solver.Add(
                sum(x[i, j] for j in range(n_receivers)) <= sources[i].get('capacity', float('inf'))
            )
        
        # 2. Alıcı talebi
        for j in range(n_receivers):
            solver.Add(
                sum(x[i, j] for i in range(n_sources)) >= receivers[j].get('demand', 0)
            )
        
        # Amaç fonksiyonu: Toplam maliyeti minimize et
        objective = solver.Objective()
        for i in range(n_sources):
            for j in range(n_receivers):
                cost = cost_matrix[i, j]
                objective.SetCoefficient(x[i, j], cost)
        objective.SetMinimization()
        
        # Çöz
        solver.SetTimeLimit(self.time_limit * 1000)
        status = solver.Solve()
        
        solve_time = (time.time() - start_time) * 1000
        
        # Sonuçları topla
        if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
            assignments = []
            total_cost = 0
            total_distance = 0
            
            for i in range(n_sources):
                for j in range(n_receivers):
                    quantity = x[i, j].solution_value()
                    if quantity > 0.01:  # Threshold
                        cost = quantity * cost_matrix[i, j]
                        assignments.append({
                            'source_id': sources[i]['id'],
                            'receiver_id': receivers[j]['id'],
                            'quantity': round(quantity, 2),
                            'cost': round(cost, 2)
                        })
                        total_cost += cost
            
            return OptimizationResult(
                total_cost=round(total_cost, 2),
                total_distance=0,  # Ayrıca hesaplanabilir
                assignments=assignments,
                solver_status='optimal' if status == pywraplp.Solver.OPTIMAL else 'feasible',
                solve_time_ms=solve_time
            )
        else:
            return OptimizationResult(
                total_cost=float('inf'),
                total_distance=0,
                assignments=[],
                solver_status='infeasible',
                solve_time_ms=solve_time
            )
    
    def _greedy_assignment(
        self,
        sources: List[Dict],
        receivers: List[Dict],
        cost_matrix: np.ndarray
    ) -> OptimizationResult:
        """OR-Tools yoksa greedy çözüm"""
        assignments = []
        total_cost = 0
        
        # Her alıcı için en ucuz kaynağı bul
        source_remaining = {i: s.get('capacity', float('inf')) for i, s in enumerate(sources)}
        
        for j, receiver in enumerate(receivers):
            demand = receiver.get('demand', 0)
            
            while demand > 0:
                # En ucuz müsait kaynağı bul
                best_i = None
                best_cost = float('inf')
                
                for i in range(len(sources)):
                    if source_remaining[i] > 0 and cost_matrix[i, j] < best_cost:
                        best_cost = cost_matrix[i, j]
                        best_i = i
                
                if best_i is None:
                    break
                
                # Atama yap
                quantity = min(demand, source_remaining[best_i])
                cost = quantity * cost_matrix[best_i, j]
                
                assignments.append({
                    'source_id': sources[best_i]['id'],
                    'receiver_id': receiver['id'],
                    'quantity': round(quantity, 2),
                    'cost': round(cost, 2)
                })
                
                source_remaining[best_i] -= quantity
                demand -= quantity
                total_cost += cost
        
        return OptimizationResult(
            total_cost=round(total_cost, 2),
            total_distance=0,
            assignments=assignments,
            solver_status='greedy'
        )
    
    # =========================================================================
    # VEHİCLE ROUTING PROBLEM
    # =========================================================================
    
    def solve_vrp(
        self,
        depot: Tuple[float, float],
        locations: List[Tuple[float, float]],
        demands: List[int],
        vehicle_capacity: int,
        num_vehicles: int,
        distance_matrix: np.ndarray
    ) -> OptimizationResult:
        """
        Vehicle Routing Problem çözümü
        
        Args:
            depot: Depo koordinatları
            locations: Teslimat noktaları
            demands: Her noktanın talebi
            vehicle_capacity: Araç kapasitesi
            num_vehicles: Araç sayısı
            distance_matrix: Mesafe matrisi (depot dahil)
        """
        if not self.ortools_available:
            raise AtikAIError("VRP için OR-Tools gerekli")
        
        from ortools.constraint_solver import routing_enums_pb2
        from ortools.constraint_solver import pywrapcp
        import time
        
        start_time = time.time()
        
        n = len(locations) + 1  # +1 for depot
        
        # Routing model
        manager = pywrapcp.RoutingIndexManager(n, num_vehicles, 0)
        routing = pywrapcp.RoutingModel(manager)
        
        # Distance callback
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(distance_matrix[from_node, to_node] * 1000)  # km to m
        
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        
        # Kapasite kısıtı
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            if from_node == 0:
                return 0
            return demands[from_node - 1]
        
        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  # slack
            [vehicle_capacity] * num_vehicles,
            True,  # start cumul to zero
            'Capacity'
        )
        
        # Çözüm parametreleri
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.seconds = self.time_limit
        
        # Çöz
        solution = routing.SolveWithParameters(search_parameters)
        
        solve_time = (time.time() - start_time) * 1000
        
        if solution:
            routes = []
            total_distance = 0
            
            for vehicle_id in range(num_vehicles):
                route = []
                index = routing.Start(vehicle_id)
                
                while not routing.IsEnd(index):
                    node = manager.IndexToNode(index)
                    route.append(node)
                    index = solution.Value(routing.NextVar(index))
                
                route.append(manager.IndexToNode(index))  # End depot
                routes.append(route)
                
                # Route distance
                route_distance = 0
                for i in range(len(route) - 1):
                    route_distance += distance_matrix[route[i], route[i+1]]
                total_distance += route_distance
            
            return OptimizationResult(
                total_cost=0,  # Ayrıca hesaplanabilir
                total_distance=round(total_distance, 2),
                assignments=[],
                routes=routes,
                solver_status='optimal',
                solve_time_ms=solve_time
            )
        else:
            return OptimizationResult(
                total_cost=float('inf'),
                total_distance=0,
                assignments=[],
                routes=[],
                solver_status='no_solution',
                solve_time_ms=solve_time
            )
    
    # =========================================================================
    # MALİYET MİNİMİZASYONU
    # =========================================================================
    
    def minimize_total_cost(
        self,
        matches: List[Dict],  # Potansiyel eşleşmeler
        max_assignments: int = None
    ) -> OptimizationResult:
        """
        Toplam maliyeti minimize eden eşleşme seti bul
        
        Args:
            matches: [{source_id, receiver_id, cost, quantity, profit}]
            max_assignments: Maksimum eşleşme sayısı
        """
        if not matches:
            return OptimizationResult(
                total_cost=0,
                total_distance=0,
                assignments=[],
                solver_status='empty'
            )
        
        # Kârlı eşleşmeleri filtrele
        profitable = [m for m in matches if m.get('profit', 0) > 0]
        
        # Kâra göre sırala
        profitable.sort(key=lambda x: x.get('profit', 0), reverse=True)
        
        # Limit uygula
        if max_assignments:
            profitable = profitable[:max_assignments]
        
        # Sonuç
        assignments = []
        total_cost = 0
        total_distance = 0
        
        for match in profitable:
            assignments.append({
                'source_id': match['source_id'],
                'receiver_id': match['receiver_id'],
                'quantity': match.get('quantity', 0),
                'cost': match.get('cost', 0),
                'profit': match.get('profit', 0)
            })
            total_cost += match.get('cost', 0)
            total_distance += match.get('distance', 0)
        
        return OptimizationResult(
            total_cost=round(total_cost, 2),
            total_distance=round(total_distance, 2),
            assignments=assignments,
            solver_status='greedy'
        )
