const REQUIRED_FIELDS = [
  "Clip for #3", "Clip for #2", "#3 label", "#2 label",
  "Top 3 topic", "YouTube channel", "Public upload approval"
];

function onFormSubmit(e) {
  const values = e.namedValues || {};
  REQUIRED_FIELDS.forEach((field) => {
    if (!values[field] || !values[field][0]) throw new Error("Missing form field: " + field);
  });

  const props = PropertiesService.getScriptProperties();
  const owner = props.getProperty("GITHUB_OWNER");
  const repo = props.getProperty("GITHUB_REPO");
  const token = props.getProperty("GITHUB_TOKEN");
  if (!owner || !repo || !token) throw new Error("GitHub Script Properties are incomplete.");

  const payload = {
    event_type: "shorts_submission",
    client_payload: {
      clip_3_file_id: driveFileId(values["Clip for #3"][0]),
      clip_2_file_id: driveFileId(values["Clip for #2"][0]),
      label_3: values["#3 label"][0],
      label_2: values["#2 label"][0],
      topic: values["Top 3 topic"][0],
      channel: values["YouTube channel"][0],
      public_approval: values["Public upload approval"][0]
    }
  };

  const response = UrlFetchApp.fetch(
    `https://api.github.com/repos/${owner}/${repo}/dispatches`,
    {
      method: "post",
      contentType: "application/json",
      headers: {
        Authorization: "Bearer " + token,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    }
  );
  if (response.getResponseCode() !== 204) {
    throw new Error("GitHub dispatch failed: " + response.getContentText());
  }
}

function driveFileId(value) {
  const match = String(value).match(/[-\w]{20,}/);
  if (!match) throw new Error("Could not read Google Drive file ID.");
  return match[0];
}
