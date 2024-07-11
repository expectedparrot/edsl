from typing import Optional


def count_query(field):
    return f"""SELECT 
                {field}, 
                COUNT(*) as number 
                FROM self 
                GROUP BY {field}
                """


def get_options(results, field):
    question_type = results.survey.get_question(field).question_type
    if question_type in ["multiple_choice", "checkbox"]:
        return results.select(f"{field}_question_options").first()
    else:
        return None


def interpret_image(path, analysis):
    from edsl import QuestionFreeText
    from edsl import Model
    from edsl import Scenario

    s = Scenario.from_image(path)
    if isinstance(analysis, str):
        plot_question_texts = [analysis]
    elif isinstance(analysis, list):
        plot_question_texts = analysis

    scenario_list = s.replicate(len(plot_question_texts))
    scenario_list.add_list("plot_question_text", plot_question_texts)

    m = Model("gpt-4o")
    q = QuestionFreeText(
        question_text="{{ plot_question_text }}", question_name="interpretation"
    )
    results = q.by(m).by(scenario_list).run()
    return results.select("plot_question_text", "interpretation").print(
        format="rich",
        pretty_labels={
            "scenario.plot_question_text": "Question to the model",
            "answer.interpretation": "Model answer",
        },
    )


def barchart(
    results,
    field: str,
    fetch_options=True,
    xlab: Optional[str] = None,
    ylab: Optional[str] = None,
    analysis: Optional[str] = None,
    format: str = "png",
):
    labels = ""
    if xlab:
        labels += f"+ xlab('{xlab}')"
    if ylab:
        labels += f"+ ylab('{ylab}')"

    if fetch_options:
        factor_orders = {field: get_options(results, field)}
    else:
        factor_orders = None

    plot = results.ggplot2(
        f"""ggplot(data = self, aes(x = {field}, y = number)) + 
        geom_bar(stat = "identity") + 
        theme_bw() + 
        theme(axis.text.x = element_text(angle = 45, hjust = 1)) {labels}""",
        sql=count_query(field),
        factor_orders=factor_orders,
        format=format,
        filename=f"barchart_{field}.{format}",
    )
    if analysis:
        interpret_image(f"barchart_{field}.{format}", analysis)

    return plot


def theme_plot(results, field, context, themes=None, progress_bar=False):
    _, themes = results.auto_theme(
        field=field, context=context, themes=themes, progress_bar=progress_bar
    )

    themes_query = f"""
    SELECT theme, COUNT(*) AS mentions
    FROM (
          SELECT json_each.value AS theme 
          FROM self, 
          json_each({ field }_themes)
          ) 
    GROUP BY theme
    HAVING theme <> 'Other'
    ORDER BY mentions DESC
             """
    themes = results.sql(themes_query, to_list=True)

    (
        results.filter(f"{field} != ''").ggplot2(
            """ggplot(data = self, aes(x = theme, y = mentions)) + 
    geom_bar(stat = "identity") + 
    coord_flip() + 
    theme_bw()""",
            sql=themes_query,
            factor_orders={"theme": [t[0] for t in themes]},
        )
    )
