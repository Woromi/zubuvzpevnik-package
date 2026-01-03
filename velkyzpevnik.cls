\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{velkyzpevnik}[2025/08/22 Class for large A4 songbook]

% ==========================
% Base class
% ==========================
\LoadClass[a4paper]{article}

% ==========================
% Option handling
% ==========================
\DeclareOption*{%
	\PassOptionsToPackage{\CurrentOption}{zubuvzpevnik}%
}
\ProcessOptions\relax

% ==========================
% Load base package
% ==========================
\RequirePackage{zubuvzpevnik}

% ==========================
% Page layout
% ==========================
\RequirePackage[
	tmargin=0.7in,
	bmargin=0.7in,
	lmargin=0.5in,
	rmargin=0.5in
]{geometry}

% ==========================
% Song styling overrides
% ==========================
\renewcommand{\zub@lyricfont}{\ttfamily}
\renewcommand{\zub@printchord}{\ttfamily\bfseries}
\renewcommand{\zub@stitlefont}{\Huge}
\largepapertrue

% ==========================
% Images
% ==========================
\RequirePackage{pdfpages}
\RequirePackage{graphicx}
\graphicspath{{img/}}

% ==========================
% Header/Footer
% ==========================
\RequirePackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{\thepage} % Page numbers on outer corners
\renewcommand{\headrulewidth}{0pt} % no header line
\renewcommand{\footrulewidth}{0pt} % no footer line

% ==========================
% Front cover
% ==========================
\newcommand{\makefrontcover}{%
	\pagenumbering{Alph}
	\pagestyle{empty}
	\begin{titlepage}
		\centering
		\null\vfill
		{\fontsize{62}{65}\bfseries\setmainfont{Roboto Bold} \@title\par}
		\vfill
		\begin{center}
			\makebox[\textwidth]{\includegraphics[width=\paperwidth]{zubuvzpevnik}}
		\end{center}
		\vfill
		{\Large\setmainfont{Roboto Bold} \@author\par}
		{\Large\setmainfont{Roboto Bold} \today\par}
		\vfill
	\end{titlepage}

	% Inside front cover = TOC
	\clearpage
	\pagestyle{empty}
	\pagenumbering{roman}
	{\large \showindex[1]{Obsah}{obsah}}
	{\large \showindex[2]{Obsah podle interpreta}{obsahAutor}}
	% TODO: Obsah interpretu prohazuje slova v nazvu kapel (razeni podle prijmeni)

	% Start page numbering from the following page
	\clearpage
	\pagenumbering{arabic}
	\pagestyle{fancy}
}

\endinput
