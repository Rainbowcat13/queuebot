import random
from time import time


class Prior:
    
    k = [  # by default
        1,  # 0. readme
        2,  # 1. hello world
        2,  # 2. sum
        2,  # 3. reverse
        2,  # 4. wordstat
        1,  # 5. scanner
        2,  # 6. wordstat++
        2,  # 7. markdown
        1,  # 8. championship
    ]

    k_mod = {}
    penalty = {}

    def __init__(self):
        self.load_from_db()

    def load_from_db(self):
        # take from db and replace coefficients with loaded one
        pass

    def get_all(self):
        # should be used to show whole array to admins
        return self.k.copy()
    
    def set_k(self, task_id: int, k: int):
        while len(self.k) <= task_id:
            self.k.append(1)
            
        self.k_mod[task_id] = k
        
    def apply_k_mod(self):
        self.load_from_db()
        
        # should be called each 30 minutes to recalc coefficients
        # (even with estimated_time = 0 and before shutdown to apply all changes)
        
        for i, j in self.k_mod.items():
            self.k[i] = j

    def get_penalties(self):
        return self.penalty

    def get_penalty(self, user_id: int, task_id: int) -> int:
        if user_id not in self.penalty:
            return 1
        if task_id not in self.penalty[user_id]:
            return 1
        return self.penalty[user_id][task_id]

    def incr_penalty(self, user_id: int, task_id: int):
        if user_id not in self.penalty:
            self.penalty[user_id] = {}
        if task_id not in self.penalty[user_id]:
            self.penalty[user_id][task_id] = 1
        self.penalty[user_id][task_id] += 1

    def calc_prior(self, user_id: int, task: int, delay_fixed: bool, estimated_time_in_minutes: int) -> float:
        return self.conv() + 2**(self.coeff_n(task) + (self.get_penalty(user_id, task)/self.coeff_k(task) if delay_fixed else (-self.coeff_d(estimated_time_in_minutes, task, user_id))))
    
    def conv(self) -> float:
        """Return tiny unique constant"""
        return -1 / time()

    def coeff_n(self, i: int) -> int:
        """Return n coefficient"""
        return i
    
    def coeff_k(self, task: int) -> int:
        """Return k coefficient
        Depends on the complexity of reviewing of the task.
        """
        return self.k[task] if task < len(self.k) else 1

    def coeff_d(self, t: int, task: int, user_id: int) -> float:
        """Return d coefficient
        Depends on estimated time
        """
        d = 1
        
        if t <= 30:
            d = 3
        elif t <= 60:
            d = 2
        
        random.seed(task * user_id)
        return d - random.uniform(0, 1)


prior = Prior()
