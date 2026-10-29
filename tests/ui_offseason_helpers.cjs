// Drive the real draft and cut controls when another suite needs a legal rollover.
async function finishOffseason(page, until) {
 const q=selector=>page.d.querySelector(selector);
 const save=()=>JSON.parse(page.w.localStorage.getItem('arcade-league-save'));
 q('#draft-button').click();
 await until(()=>Array.isArray(save().draftChoices));
 while(save().draftChoices.length<4){
  const count=save().draftChoices.length;
  q('#draft-prospects [data-draft-id]:not([disabled])').click();
  await until(()=>save().draftChoices.length===count+1);
 }
 q('#draft-close').click();q('#manage-roster').click();
 while(page.d.querySelectorAll('#roster-groups .roster-player').length>38){
  const count=save().dropped.length;
  q('#roster-groups [data-drop-id]:not([disabled])').click();q('#cut-confirm').click();
  await until(()=>save().dropped.length===count+1);
 }
}
module.exports={finishOffseason};
