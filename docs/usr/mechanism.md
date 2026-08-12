## Work Speed

```
(abnormality base work speed) * (1 + ((observation bonus) + (work speed)) / 100)
```

One Sin has a work speed of 0.3 and an observation bonus of 10, so plugging that in there an agent with 30 Temperance would wind up having a total work speed of 0.3*1.4, for a total of 0.42. If we raise that to 50, we instead get 0.48. This is a 12.5% increase from 20 points of boost, again much higher than the 4% difference the game would tell us it gave.

On a related note, the total work time equals (total # of boxes)/(work speed), gotten from the above equation. This has nothing to do with the topic at hand, but now I don't have to mention it later.

## Work Success

Finally, there's Work Success. Every 5 points of Work Success adds exactly 1% to the odds of an Agent getting a success on each box. Changes of less than 5 do nothing, they only matter in those 5 point increments. Work Success is completely accurate. Work success chance is calculated by first adding all bonuses, then checking that they don't go over 95%, then applying any penalties that may be present, before rolling for success. This means two things: that penalties are a major pain because they permanently lower the best possible chance of success, and that we always have at least a 5% chance of failing. 

The Success Rate of an Abnormality is generally identified by the following descriptors, from lowest to highest probability: Very Low (0-19%), Low (20-39%), Common (40-59%), High (60-79%) and Very High (80-95%). This Stat is displayed in an Agent's Info. Extra additions (represented as '+ x') are placed next to the value, not counting as part of the base Stat.

Every point of WorkSuccessIcon.png Success Rate grants +0.2% work success probability.

Work Speed or Speed Rate is how fast the agent will complete or fill the work gauge when working with an Abnormality. This increase the speed that an agent works, taking less time to perform the whole work, but doesn't increase the performance of the agent, meaning that they can get NE-Boxes more quickly too. This Stat is displayed in an Agent's Info. Extra additions (represented as '+ x') are placed next to the value, not counting as part of the base Stat.

Every point of WorkSpeedIcon.png Work Speed grants +1% increase in work speed.