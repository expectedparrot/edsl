import random


def default_turn_taking_generator(agent_list, speakers_so_far, **kwargs):
    """Returns the next speaker in the list of agents, in order. If no speakers have spoken yet, returns the first agent in the list."""
    if len(speakers_so_far) == 0:
        return agent_list[0]
    most_recent_speaker = speakers_so_far[-1]
    index = agent_list.index(most_recent_speaker)
    return agent_list[(index + 1) % len(agent_list)]


def turn_taking_generator_with_focal_speaker(
    agent_list, speakers_so_far, focal_speaker_index, **kwargs
):
    """Returns the focal speaker first, then the next speaker in the list of agents sequentially, going back to the focal speaker after the last agent has spoken. If no speakers have spoken yet, returns the focal speaker.
    This would be appropriate for say, a an auction where the auctioneer always speaks first, and then the next person in line speaks, and then the auctioneer speaks again.
    """
    if len(speakers_so_far) == 0:
        return agent_list[focal_speaker_index]

    most_recent_speaker = speakers_so_far[-1]
    if most_recent_speaker == agent_list[focal_speaker_index]:
        non_focal_agents = [
            a for a in agent_list if a != agent_list[focal_speaker_index]
        ]
        non_focal_speakers = [
            a for a in speakers_so_far if a != agent_list[focal_speaker_index]
        ]
        return default_turn_taking_generator(
            agent_list=non_focal_agents, speakers_so_far=non_focal_speakers
        )
    else:
        return agent_list[focal_speaker_index]


def random_turn_taking_generator(agent_list, speakers_so_far, **kwargs):
    """Returns a random speaker from the list of agents, but ensuring no agent speaks twice in a row.
    If no speakers have spoken yet, returns a random agent."""
    if len(speakers_so_far) == 0:
        return random.choice(agent_list)
    else:
        most_recent_speaker = speakers_so_far[-1]
    return random.choice([a for a in agent_list if a != most_recent_speaker])


def random_inclusive_generator(agent_list, speakers_so_far, **kwargs):
    """Returns a random speaker from the list of agents, but ensuring no agent speaks twice in a row and that
    every agent has spoken before the same agent speaks again.
    """
    if len(speakers_so_far) > 0:
        most_recent_speaker = speakers_so_far[-1]
    else:
        most_recent_speaker = None

    lookback_length = len(speakers_so_far) % len(agent_list)

    if lookback_length == 0:
        eligible_agents = agent_list[:]
    else:
        eligible_agents = [
            a for a in agent_list if a not in speakers_so_far[-lookback_length:]
        ]

    # don't have the same speaker twice in a row
    if most_recent_speaker in eligible_agents:
        eligible_agents.pop(eligible_agents.index(most_recent_speaker))

    return random.choice(eligible_agents)


def speaker_closure(agent_list, generator_function, focal_speaker_index=None):
    speakers_so_far = []
    focal_speaker_index = focal_speaker_index

    def next_speaker_generator():
        speaker = generator_function(
            agent_list=agent_list,
            speakers_so_far=speakers_so_far,
            focal_speaker_index=focal_speaker_index,
        )
        speakers_so_far.append(speaker)
        return speaker

    return next_speaker_generator


# speaker_gen = speaker_closure(agent_list = ['Alice', 'Bob', 'Charlie', "Mr.X"],
#                               generator_function = turn_taking_generator_with_focal_speaker,
#                               focal_speaker_index = 3)

# for _ in range(30):
#     print(speaker_gen())
