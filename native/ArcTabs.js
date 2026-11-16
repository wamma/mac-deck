// Fixed read-only JXA. No user input, active tab lookup, activation or tab mutations.
ObjC.import('AppKit');
function run() {
  try {
    const running=$.NSRunningApplication.runningApplicationsWithBundleIdentifier('company.thebrowser.Browser');
    if(Number(running.count)!==1)return JSON.stringify({status:'not_running',windows:[]});
    const instance=running.objectAtIndex(0),pid=Number(instance.processIdentifier);
    if(instance.terminated)return JSON.stringify({status:'not_running',windows:[]});
    const arc=Application(pid),windows=arc.windows(),rows=[];let total=0,truncated=false;
    for(let i=0;i<windows.length;i++){
      if(i>=50){truncated=true;break;}
      const win=arc.windows[i],tabs=win.tabs(),items=[];
      for(let j=0;j<tabs.length;j++){
        if(total>=2000){truncated=true;break;}
        const tab=win.tabs[j];items.push({id:String(tab.id()),title:String(tab.title()).slice(0,512),url:String(tab.url()).slice(0,8192)});total++;
      }
      rows.push({id:String(win.id()),tabs:items});
    }
    if(instance.terminated)return JSON.stringify({status:'not_running',windows:[]});
    return JSON.stringify({status:'ok',windows:rows,truncated:truncated});
  }catch(error){return JSON.stringify({status:'error',code:Number(error.errorNumber||error.number)||null});}
}
