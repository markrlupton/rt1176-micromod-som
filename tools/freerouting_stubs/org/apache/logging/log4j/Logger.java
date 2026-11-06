package org.apache.logging.log4j;
public class Logger {
    public void trace(String m) {}
    public void info(String m) { System.out.println(m); }
    public void warn(String m) { System.err.println("WARN " + m); }
    public void error(String m) { System.err.println("ERROR " + m); }
    public void error(String m, Throwable t) { System.err.println("ERROR " + m + " " + t); }
}
