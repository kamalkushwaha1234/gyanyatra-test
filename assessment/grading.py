class Grading:
    description: str
    range: any

    def __init__(self, description: str, range: any):
        self.description = description
        self.range = range

    def __str__(self):
        return f"({self.range.start}-{self.range.stop})"


GRADING = {
    "A1": Grading(
        """At A1 (Elementary) level represent the early stages of English proficiency, indicating limited or no knowledge and encompassing basic skills for everyday communication""",
        range(0, 30),
    ),
    "A2": Grading(
        """At A2 (Pre-Intermediate)  level, individuals can understand basic expressions and communicate in a simple manner. They can comprehend sentences and frequently-used expressions, communicate in simple, everyday tasks, and describe aspects of their past and environment.""",
        range(30, 42),
    ),
    "B1": Grading(
        """At B1 (Intermediate)  level, individuals can understand and produce text on familiar topics, give opinions, and provide descriptions. They can understand the main points of clear texts, cope with situations in various contexts, and produce simple, coherent texts about familiar topics.""",
        range(42, 58),
    ),
    "B2": Grading(
        """At B2 (Upper Intermediate)  level, individuals can understand complex texts, interact fluently and spontaneously, and produce clear, detailed text on a wide range of subjects. They can engage in discussions and express viewpoints on topical issues.""",
        range(58, 76),
    ),
    "C1": Grading(
        """At C1 (Advanced) level, individuals can understand a wide range of demanding texts, express themselves fluently and spontaneously, and use language flexibly and effectively for social, academic, and professional purposes. They can produce clear, well-structured, and detailed text on complex subjects.""",
        range(76, 83),
    ),
    "C2": Grading(
        """At C2 (Proficient) level, individuals can understand and express virtually everything with ease, summarizing information from different sources, and presenting it coherently. They can express themselves spontaneously, fluently, and precisely, even in complex situations.""",
        range(83, 91),
    ),
}
