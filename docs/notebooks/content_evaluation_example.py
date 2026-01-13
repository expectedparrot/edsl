import marimo

__generated_with = "0.14.16"
app = marimo.App()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # Self-evaluation
        In this notebook we prompt a model to describe an image and then evaluate the description.

        This involves using an image as a [scenario](https://docs.expectedparrot.com/en/latest/scenarios.html) of survey questions, and [piping](https://docs.expectedparrot.com/en/latest/notebooks/piping_comments.html) the answer to a question into another question.

        We also show how to use [FileStore](https://docs.expectedparrot.com/en/latest/filestore.html) to post and retrieve files to [Coop](https://docs.expectedparrot.com/en/latest/coop.html) for ease of sharing data and other content used with surveys.

        Please see the [docs](https://docs.expectedparrot.com) for more examples and details on all of these methods.

        New: Polly Link: [https://www.expectedparrot.com/polly/share/54458464-7b42-4a01-af8c-00d3ddd8138f](https://www.expectedparrot.com/polly/share/54458464-7b42-4a01-af8c-00d3ddd8138f)
        """
    )
    return


@app.cell
def _():
    from edsl import QuestionFreeText, Survey, Scenario, Model, FileStore
    return FileStore, Model, QuestionFreeText, Scenario, Survey


@app.cell
def _(Model):
    m = Model("gemini-2.5-flash")
    return (m,)


@app.cell
def _(QuestionFreeText):
    q1 = QuestionFreeText(
        question_name = "describe",
        question_text = "Describe this image: {{ scenario.image }}"
    )
    return (q1,)


@app.cell
def _(QuestionFreeText):
    q2 = QuestionFreeText(
        question_name = "improvements",
        question_text = """
        Consider the following image and description of it.
        In what ways could this description be improved?
        Image: {{ scenario.image }}
        Description: {{ describe.answer }}
        """
    )
    return (q2,)


@app.cell
def _(FileStore):
    file = FileStore("johnhorton/ep-logo-v-2")
    return (file,)


@app.cell
def _(file):
    file.view()
    return


@app.cell
def _(Survey, q1, q2):
    survey = Survey([q1,q2])
    return (survey,)


@app.cell
def _(survey):
    survey.push(visibility = "public", description = "Image labeling example", alias = "image-labeling-example")
    return


@app.cell
def _(survey):
    survey.show_flow()
    return


@app.cell
def _(Scenario, file):
    # Cell tags: skip-execution
    # creating a scenario
    s = Scenario({
        "image":file,
        "image_id":"parrot" # metadata for results
    })
    return (s,)


@app.cell
def _(m, s, survey):
    # Cell tags: skip-execution
    results = survey.by(s).by(m).run()
    return (results,)


@app.cell
def _(results):
    # Cell tags: skip-execution
    results.columns
    return


@app.cell
def _(results):
    # Cell tags: skip-execution
    results.select("model", "image_id", "describe", "improvements")
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
