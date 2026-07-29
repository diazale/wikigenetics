#' End-of-line chart theme
#'
#' A minimal \pkg{ggplot2} theme that reproduces the visual style of a line
#' chart with labels placed at the end of each line (in the style of the
#' R Graph Gallery's "line chart with labels at end of line"). The theme uses
#' a light grey background, removes axis titles, mutes the axis text, and draws
#' only horizontal major grid lines. It generalizes to arbitrary x and y axes,
#' so the same visual style can be applied to other geometries such as bar
#' plots.
#'
#' @details
#' The horizontal grid lines are produced through \code{panel.grid.major.y}
#' rather than manually drawn segments, so they automatically track whatever
#' breaks the y-scale generates. This makes the theme reusable across plots
#' with different data ranges and axis types. Vertical grid lines are disabled
#' by default; to enable them (e.g. for a bar plot), add
#' \code{panel.grid.major.x = ggplot2::element_line(...)} after the theme.
#'
#' The function builds on \code{\link[ggplot2]{theme_minimal}} and uses
#' \code{\%+replace\%} together with \code{complete = TRUE} so the result
#' behaves as a complete, standalone theme. Theme elements added afterwards
#' with \code{+ theme(...)} therefore modify it predictably.
#'
#' @param base_family Character. Base font family for all text elements.
#'   Defaults to \code{"sans"}.
#' @param base_size Numeric. Base font size in points, passed to
#'   \code{\link[ggplot2]{theme_minimal}}. Defaults to \code{11}.
#'
#' @return A complete \pkg{ggplot2} theme object (class \code{"theme"} and
#'   \code{"gg"}) that can be added to a plot with \code{+}.
#'
#' @seealso \code{\link[ggplot2]{theme_minimal}},
#'   \code{\link[ggplot2]{theme}}
#'
#' @examples
#' library(ggplot2)
#'
#' # Line chart
#' ggplot(economics, aes(date, unemploy)) +
#'   geom_line(linewidth = .8) +
#'   theme_endline()
#'
#' # Bar plot - same visual style, no changes needed
#' ggplot(mpg, aes(class)) +
#'   geom_bar(fill = "grey50") +
#'   theme_endline()
#'
#' # Enable vertical grid lines on top of the theme
#' ggplot(mpg, aes(class)) +
#'   geom_bar(fill = "grey50") +
#'   theme_endline() +
#'   theme(panel.grid.major.x = element_line(color = "grey91", linewidth = .5))
#'
#' @importFrom ggplot2 theme_minimal theme element_blank element_text
#'   element_line element_rect margin unit %+replace%
#' @export
theme_endline <- function(base_family = "sans", base_size = 11) {
  ggplot2::theme_minimal(base_family = base_family, base_size = base_size) %+replace%
    ggplot2::theme(
      # --- Axis titles and text ---
      #axis.title        = ggplot2::element_blank(),
      axis.text         = ggplot2::element_text(color = "grey40"),
      #axis.text.x       = ggplot2::element_text(size = 11, margin = ggplot2::margin(t = 5)),
      #axis.text.y       = ggplot2::element_text(size = 10, margin = ggplot2::margin(r = 5)),
      
      # --- Axis ticks ---
      axis.ticks        = ggplot2::element_line(color = "grey91", linewidth = .5),
      axis.ticks.length = ggplot2::unit(0.3, "lines"),
      
      # --- Grid lines (horizontal only; replaces manual geom_segment) ---
      panel.grid.minor   = ggplot2::element_blank(),
      panel.grid.major.x = ggplot2::element_blank(),
      panel.grid.major.y = ggplot2::element_line(color = "grey80", linewidth = .5),
      
      # --- Backgrounds and margins ---
      plot.margin       = ggplot2::margin(20, 100, 20, 40),
      plot.background   = ggplot2::element_rect(fill = "grey98", color = "grey98"),
      panel.background  = ggplot2::element_rect(fill = NA, color = NA),
      
      # --- Title ---
      plot.title        = ggplot2::element_text(
        color = "grey10", size = 14, face = "bold",
        margin = ggplot2::margin(t = 15), hjust = 0
      ),
      plot.title.position = "plot",
      
      # --- Legend ---
      legend.position   = "none",
      
      complete = TRUE
    )
}