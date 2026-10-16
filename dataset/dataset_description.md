# Dataset Description — Telemedicine Workload Offloader

## Primary Dataset: RIPE Atlas Ping Measurements (Network Latency Traces)
- **Source**: RIPE NCC (Réseaux IP Européens Network Coordination Centre), RIPE Atlas global measurement network
- **URL**: https://atlas.ripe.net
- **Total Measurements**: 2,830,022 records
- **Data Size**: ~201 MB (uncompressed CSV / JSON time series format)
- **Probes**: 10,000+ probes across 6 continents
- **License**: Public measurement data accessible under RIPE Atlas Service Terms and Conditions (free for academic, research, and educational use)

### Features per Timestep:
1. current_latency_ms: Round-Trip Time (RTT in ms, measured directly by ICMP ping probes)
2. packet_loss_pct: Packet loss percentage ((sent - rcvd) / sent * 100, measured directly)
3. jitter_ms: Jitter (max RTT - min RTT in ms, measured directly)
4. andwidth_mbps: Estimated bandwidth capacity (derived via inverse RTT capacity heuristic)
5. signal_strength_dbm: Estimated wireless signal strength (derived via latency attenuation model)

## Secondary Dataset: PhysioNet BIDMC Congestive Heart Failure Database
- **Source**: PhysioNet / BIDMC (Beth Israel Deaconess Medical Center)
- **Usage**: De-identified ICU telemetry vitals (ECG, SpO2, HR) for clinical criticality validation
