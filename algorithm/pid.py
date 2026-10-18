class PIDController:
    """
    A PID controller for smooth robot operation that adjusts in real time to physical responses.

    The PID controller takes a kp (proportional constant), ki (integral constant), and kd (derivative constant)
    and adjusts to error in real time. For example, if the robot is trying to drive forward, and there is an
    unexpected force pushing it backwards, PID will adjust drive speed to go forward with more power.

    Attributes:
        kp (float): Proportional constant.
        ki (float): Integral constant.
        kd (float): Derivative constant.
        min_out (float): Minimum output of the drive.
        max_out (float): Maximum output of the drive.
        max_windup (float): Caps the absolute value of the integral.
        prev_error (float): The error at the previous step.
        integral (float): Accumulation of error over time.
    """

    def __init__(
        self,
        kp: float,
        ki: float,
        kd: float,
        output_limits: tuple[float, float] = (-1.0, 1.0),
        max_windup: float = 0.5,
    ):
        """
        Initializes the PID controller with tuning variables and constraints.

        Args:
            kp: Proportional gain constant.
            ki: Integral gain constant.
            kd: Derivative gain constant.
            output_limits: A tuple containing the minimum and maximum allowed
                control output values. Defaults to (-1.0, 1.0).
            max_windup: The maximum absolute value the integrated error can
                accumulate to prevent integral windup. Defaults to 0.5.

        Example:
            PIDController(kp=0.01, ki=0.000, kd=0.0005, output_limits=(-1.0, 1.0))
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd

        # Anti-windup and output constraints
        self.min_out, self.max_out = output_limits
        self.max_windup = max_windup

        # State variables
        self.prev_error = 0.0
        self.integral = 0.0

    def update(self, error: float, dt: float) -> float:
        """
        Computes the clamped output for this step and updates integral/prev_error. It also returns 0.0 when dt <= 0.

        Args:
            error: difference between a desired setpoint (SP) and a measured process variable (PV)
            dt: change in time

        Returns:
            float: calculated control output for the robot
        """
        if dt <= 0.0:
            return 0.0

        # Proportional
        p = self.kp * error

        # Integral (with anti-windup clamping)
        self.integral += error * dt
        # Prevent the integral from building up infinitely if the bot is physically stuck
        self.integral = max(min(self.integral, self.max_windup), -self.max_windup)
        i = self.ki * self.integral

        # Derivative
        d = self.kd * (error - self.prev_error) / dt

        # Save current error for next derivative calculation
        self.prev_error = error

        # Calculate total output and clamp to motor limits (-1 to 1)
        output = p + i + d
        return max(min(output, self.max_out), self.min_out)

    def reset(self) -> None:
        """
        Clears the integral and error memory.
        """
        self.prev_error = 0.0
        self.integral = 0.0
