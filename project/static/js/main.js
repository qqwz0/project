(function () {
  "use strict";
  // Initialize when DOM loads
  document.addEventListener("DOMContentLoaded", () => {
    // Close popup on escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeTeacherPopup();
      }
    });

    // Simplified scroll handler
    function handleScroll() {
      const header = document.getElementById("header");
      if (!header) return;

      if (window.scrollY > 20) {
        header.classList.add("scrolled-header");
      } else {
        header.classList.remove("scrolled-header");
      }
    }

    document.addEventListener("scroll", handleScroll);
    window.addEventListener("load", handleScroll);

    // Threaded replies in file comments
    document.body.addEventListener("click", function (e) {
      if (e.target && e.target.classList.contains("reply-btn")) {
        const parentId = e.target.getAttribute("data-parent-id");
        const author = e.target.getAttribute("data-author") || "";

        const container = e.target.closest(".file-comments");
        if (!container) {
          return;
        }
        const form = container.querySelector("form.reply-form");
        if (!form) {
          return;
        }
        const parentInput = form.querySelector(".reply-parent-input");
        const pill = form.querySelector(".replying-pill");
        const pillText = form.querySelector(".replying-to");

        if (parentInput) parentInput.value = parentId;
        if (pill && pillText) {
          pillText.textContent = "Відповідь для: " + author;
          pill.style.display = "inline-flex";
        }
        const textarea = form.querySelector('textarea[name="text"]');
        if (textarea) {
          textarea.focus();
        }
      }
      if (e.target && e.target.classList.contains("replying-clear")) {
        const form = e.target.closest("form.reply-form");
        if (!form) return;
        const parentInput = form.querySelector(".reply-parent-input");
        if (parentInput) parentInput.value = "";
        const pill = form.querySelector(".replying-pill");
        if (pill) {
          pill.style.display = "none";
        }
      }
    });

    // AJAX submit for bottom comment form (student/teacher unified)
    document.body.addEventListener("submit", async function (e) {
      const form = e.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (!form.classList.contains("reply-form")) return;

      e.preventDefault();

      try {
        const action = form.getAttribute("action");
        const fd = new FormData(form);
        const csrf = form.querySelector(
          'input[name="csrfmiddlewaretoken"]'
        ).value;

        const res = await fetch(action, {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrf,
          },
          body: fd,
        });

        const data = await res.json();
        if (data && data.success) {
          // Build new comment DOM
          const list = form
            .closest(".file-comments")
            .querySelector(".comments-list");
          if (list) {
            const item = document.createElement("div");
            item.className = "comment-block student-bg";

            // Check if this is a reply (has parent_id)
            const parentId = form.querySelector(".reply-parent-input").value;
            let quotedHtml = "";
            if (parentId) {
              // Find the parent comment to quote
              const parentComment = list.querySelector(
                `[data-comment-id="${parentId}"]`
              );
              if (parentComment) {
                const parentAuthor =
                  parentComment.querySelector(".comment-author").textContent;
                const parentDate =
                  parentComment.querySelector(".comment-date").textContent;
                const parentText =
                  parentComment.querySelector(".comment-text").textContent;
                const shortText =
                  parentText.length > 100
                    ? parentText.substring(0, 100) + "..."
                    : parentText;

                quotedHtml = `
                    <div class="quoted-comment">
                      <div class="quoted-comment-header">
                        <span class="quoted-author">${parentAuthor}</span>
                        <span class="quoted-date">${parentDate}</span>
                      </div>
                      <p class="quoted-text">${shortText.replace(
                        /</g,
                        "&lt;"
                      )}</p>
                    </div>
                  `;
              }
            }

            item.innerHTML = `
                ${quotedHtml}
                <div class="comment-header">
                  <span class="comment-author">${data.author}</span>
                  <span class="comment-date">${data.created_at}</span>
                </div>
                <p class="comment-text">${(data.text || "").replace(
                  /</g,
                  "&lt;"
                )}</p>
              `;
            list.appendChild(item);
          }
          // reset form
          form.querySelector('textarea[name="text"]').value = "";
          const parentInput = form.querySelector(".reply-parent-input");
          if (parentInput) parentInput.value = "";
          const pill = form.querySelector(".replying-pill");
          if (pill) pill.style.display = "none";
        } else {
          console.error("Comment error", data);
        }
      } catch (err) {
        console.error("Comment submit failed", err);
      }
    });
  });
})();