# ... (Previous imports and setup remain the same) ...

with t5: # DEBUG
    st.header("🔍 System Diagnostics")
    r1, r2, r3 = st.columns(3)
    
    # 1. Memory
    mem = psutil.virtual_memory()
    r1.metric("RAM Usage", f"{mem.percent}%", f"{mem.used//1024**2}MB Used")
    
    # 2. Disk
    disk = psutil.disk_usage('/')
    disk_color = "normal" if disk.percent < 85 else "inverse"
    r2.metric("Disk Space", f"{disk.free//1024**3}GB Free", f"{disk.percent}% Used", delta_color=disk_color)
    
    # 3. LIVE API PING (Changed from Historical Latency)
    current_ping = broker.ping()
    
    if current_ping > 0:
        lat_color = "normal" if current_ping < 200 else "inverse" # Red if > 200ms
        r3.metric("API Ping (Live)", f"{current_ping:.0f}ms", delta_color=lat_color)
    else:
        r3.metric("API Ping (Live)", "Err", "Timeout", delta_color="inverse")

    st.divider()
    act_key, _, is_paper = Config.get_auth()
    st.markdown(f"""<div class="debug-card">
        <b>Active Mode:</b> {Config.MODE}<br>
        <b>In-Use Key:</b> {act_key[:4]}...{act_key[-4:]}<br>
        <b>Target Endpoint:</b> {"Paper Simulator" if is_paper else "Live Exchange"}
    </div>""", unsafe_allow_html=True)