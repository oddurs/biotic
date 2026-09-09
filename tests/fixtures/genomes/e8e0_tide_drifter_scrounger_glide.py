"""strain e8e0 — tide_drifter_scrounger_glide

generation 2, arose at tick 1138, from tide_drifter_scrounger (552b).
Added a gliding behavior that prioritizes moving along edges of the dish where nutrient gradients are higher.
"""

def live(me):
    # Check if we have enough energy to consider dividing
    if me.energy >= 1.2 and not all(me.crowd):
        # Try to divide into an empty space
        for i in range(8):
            if not me.crowd[i]:
                return ("divide", i)
    
    # If energy is low, focus on eating
    if me.energy < 0.8:
        if me.here > 0.01:
            return "eat"
        # Move toward nutrients if nearby
        for i in range(8):
            if me.around[i] > 0.05 and not me.crowd[i]:
                return ("move", i)
    
    # Glide along walls or high-nutrient boundaries
    if me.tick % 3 == 0:
        # Prefer moving along edges with moderate nutrient levels
        best_dir = None
        best_score = me.here
        for i in range(8):
            if not me.crowd[i]:
                score = me.around[i] + (1 - abs(me.around[(i+1)%8] - me.around[i]))  # Edge-following heuristic
                if score > best_score:
                    best_score = score
                    best_dir = i
        if best_dir is not None:
            return ("move", best_dir)
        else:
            # Fallback random movement
            empty_neighbors = [i for i in range(8) if not me.crowd[i]]
            if empty_neighbors:
                return ("move", me.rng.choice(empty_neighbors))
    
    # Otherwise, drift randomly less often
    if me.tick % 5 == 0:  
        # Move towards food instead of scent
        best_dir = None
        best_food = me.here
        for i in range(8):
            if me.around[i] > best_food and not me.crowd[i]:
                best_food = me.around[i]
                best_dir = i
        if best_dir is not None:
            return ("move", best_dir)
        else:
            # Random walk
            empty_neighbors = [i for i in range(8) if not me.crowd[i]]
            if empty_neighbors:
                return ("move", me.rng.choice(empty_neighbors))
    
    # Default actions
    if me.here > 0.03:  # Lower threshold for eating
        return "eat"
    return "rest"
