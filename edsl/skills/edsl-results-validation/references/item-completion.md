# Audit item completion by survey wave

A wave is a collection round identified by a study field such as `scenario.wave`. Count interviews separately in each wave, including a returning participant. For an item, the completion rate is the number of exposed interviews with a valid answer divided by the number of interviews exposed to it. Report the numerator and denominator. A zero denominator gives an undefined rate. Completion of a whole human survey is a separate respondent-level status.

Read wave, exposure metadata and answers from the **same interview rows**. This CLI query uses the saved results and starts no jobs. Check `ep results columns --file waves.ep` for the fields available in your study.

```bash
ep results select --file waves.ep --column scenario.wave --column randomization.exposure_order --column 'answer.*'
```

Establish what recorded exposure means in your study. Humanize exports can include `randomization.exposure_events[item].presented`; true and false are observations, while null or a missing entry means unknown. The human `exposure_order` contains presented items with known start times. For simulated runs, the runner can record an order based on answer completion times. Neither source guarantees a complete page-view log. Keep unknown exposure separate. Use order membership as the denominator only when it is known to enumerate every exposed item.

For complete exposure lists and numeric ratings, run the bundled audit and read back the CSV. Set the bounds to the study’s valid scale. It counts numeric answers in range, including zero, and writes a blank mean when there are no valid answers.

```bash
ep skills show edsl-results-validation --script scripts/item_completion.py --human > item_completion.py
python item_completion.py waves.ep --wave-field wave --item speed --item comfort --item reliability --min-score 0 --max-score 10 --output coverage.csv
```

If only one participant in wave two saw speed and left it blank, the speed row has one exposure, zero answers and an empty mean. Another interview’s stored speed of 4 contributes nothing when speed is absent from that interview’s complete exposure list.
