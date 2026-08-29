### High level structure conventions

### Tools
- loguru
    - Use this tool for logging. Use logging for tracing, debugging, and information.
    - Tracing (TRACE)
        - This is the level used when debugging, when a programmer needs to see what lines of code were executed on a given (possibly faulty) run.
        - Log things that are important for specifically debugging a file like "Line X starting...." "Line X done." at the TRACE level.
        - Here is an example of a logging trace line: `logger.trace("object_detection: line 5 done GO HUEY")`
    - Debugging (DEBUG)
        - This level is also used for debugging, to output information about a given run to make debugging easier for a programmer. 
        - Log things that are important for debugging when something might not be working generally like "Object Detection returned in 4.3 ms" at the DEBUG level.
        - Here is an example of a logging debug line: `logger.debug("camera: frame {} captured", frame.frame_id)`
    - Information (INFO)
        - Info level logs will be what will be outputted during actual competition. These should be essential for runtime. For example, "Camera initialized at 1920x1080, 120 fps."
        - Here is an example of a logging info line: `logger.info("camera: initialized ({}x{})", width, height)`
- uv
- black
- git
    - commit messages
    - pull requests

### Documentation Rules
- Specs for methods
- Type enforcement
- Explaination of code
- Variable/function names that make sense
    - Variable/function names should make sense without reading the rest of the code
    - Good examples:
    - Bad examples:

### AI Agent Instructions
 - Quaternions