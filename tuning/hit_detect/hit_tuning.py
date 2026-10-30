def hit_loss(huey_rad: float, huey_head: float, y: tuple[float, float]):
    hit_score = huey_rad + huey_head
    score = (y[0] - huey_rad)*(y[1] - huey_head)

