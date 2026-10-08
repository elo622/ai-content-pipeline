\# AI Content Pipeline



A modular Python pipeline that transforms source material into a finished

short-form video using AI-assisted content generation, image generation,

text-to-speech, timeline construction, and FFmpeg rendering.



The project can be run stage-by-stage for inspection and debugging or

executed automatically from beginning to end through a single pipeline runner.



\---





\## Architecture



```mermaid

flowchart TD

&#x20;   A\[Source Article] --> B\[Article Fetcher]

&#x20;   B --> C\[Script Creator]



&#x20;   C --> D\[Visual Creator]

&#x20;   C --> E\[Voiceover Creator]



&#x20;   D --> F\[Timeline]

&#x20;   E --> F



&#x20;   F --> G\[Video Creator]

&#x20;   G --> H\[Final MP4]



&#x20;   R\[Pipeline Runner] -. orchestrates .-> B

&#x20;   R -. orchestrates .-> C

&#x20;   R -. orchestrates .-> D

&#x20;   R -. orchestrates .-> E

&#x20;   R -. orchestrates .-> F

&#x20;   R -. orchestrates .-> G



&#x20;   H -. optional .-> P\[Content Publisher]

&#x20;   H -. optional .-> M\[Email Delivery]

```





\## Overview



The AI Content Pipeline takes a source article and automatically produces:



1\. Source article

2\. Narration script

3\. Generated visual assets

4\. AI-generated voiceover

5\. Media timeline

6\. Finished vertical MP4



The core pipeline is independent from publishing platforms.



Publishing and email delivery are implemented as optional integrations.



\---



\## Pipeline Architecture



```text

Source

&#x20; ↓

article\_fetcher.py

&#x20; ↓

Script

&#x20; ↓

script\_creator.py

&#x20; ↓

Visual Assets

&#x20; ↓

visual\_creator.py

&#x20; ↓

Voiceover

&#x20; ↓

voiceover\_creator.py

&#x20; ↓

Media Timeline

&#x20; ↓

timeline.py

&#x20; ↓

Video Render

&#x20; ↓

video\_creator.py

&#x20; ↓

Final MP4





Final MP4

&#x20;  ├── content\_publisher.py

&#x20;  └── email\_delivery.py

