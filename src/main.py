import machine, sys, time

try:
    import main_tank
    main_tank.start()    
except KeyboardInterrupt:
    print("Stopped by user")
    # Drop to REPL
except Exception as e:
    print("Fatal error - waiting 5s before reset")
    sys.print_exception(e)
    time.sleep(5)  # Time window to Ctrl-C
    machine.reset()