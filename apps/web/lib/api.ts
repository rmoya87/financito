let csrfToken:string|null=null;
let sessionPromise:Promise<string>|null=null;

async function ensureSession(force=false):Promise<string>{
  if(force)csrfToken=null;
  if(csrfToken)return csrfToken;
  if(!sessionPromise){
    sessionPromise=fetch('/api/v1/session',{credentials:'same-origin',cache:'no-store'})
      .then(async res=>{
        if(!res.ok)throw new Error('No se pudo iniciar la sesión local');
        const data=await res.json() as {csrf_token:string};
        csrfToken=data.csrf_token;
        return data.csrf_token;
      })
      .finally(()=>{sessionPromise=null});
  }
  return sessionPromise;
}

function friendlyStatus(status:number){
  if(status===400)return 'La información enviada no es válida.';
  if(status===401||status===403)return 'La sesión local no permite realizar esta acción.';
  if(status===404)return 'No se ha encontrado el dato solicitado.';
  if(status===409)return 'La operación necesita resolver antes una inconsistencia o un dato pendiente.';
  if(status===413)return 'El archivo es demasiado grande.';
  if(status===422)return 'Falta algún dato obligatorio o tiene un formato no válido.';
  if(status===503)return 'El servicio local o una fuente externa no está disponible en este momento.';
  return 'No se pudo completar la operación.';
}

async function parse<T>(res:Response):Promise<T>{
  if(!res.ok){
    let message=friendlyStatus(res.status);
    try{
      const data=await res.clone().json() as {detail?:unknown;message?:unknown};
      if(typeof data.detail==='string'&&data.detail.trim())message=data.detail.trim();
      else if(typeof data.message==='string'&&data.message.trim())message=data.message.trim();
      else if(Array.isArray(data.detail)){
        const fields=data.detail
          .map((x:any)=>typeof x?.msg==='string'?x.msg:null)
          .filter(Boolean);
        if(fields.length)message=fields.join(' ');
      }
    }catch{
      try{
        const text=(await res.text()).trim();
        if(text&&!text.startsWith('{')&&!text.startsWith('[')&&text.length<500)message=text;
      }catch{}
    }
    throw new Error(message);
  }
  if(res.status===204)return undefined as T;
  const text=await res.text();
  return (text?JSON.parse(text):undefined) as T;
}

export async function apiGet<T>(path:string):Promise<T>{
  await ensureSession();
  const res=await fetch(path,{credentials:'same-origin',cache:'no-store'});
  if(res.status===401){
    await ensureSession(true);
    return parse<T>(await fetch(path,{credentials:'same-origin',cache:'no-store'}));
  }
  return parse<T>(res);
}

async function mutateRequest(path:string,method:'POST'|'PATCH'|'PUT'|'DELETE',body:unknown,forceSession=false){
  const csrf=await ensureSession(forceSession);
  return fetch(path,{
    method,
    credentials:'same-origin',
    headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
    body:body===undefined?undefined:JSON.stringify(body),
  });
}

export async function apiMutate<T>(path:string,method:'POST'|'PATCH'|'PUT'|'DELETE',body?:unknown):Promise<T>{
  let res=await mutateRequest(path,method,body);
  if(res.status===401||res.status===403){
    // A different tab or an expired browser cookie may have invalidated the
    // token held in this JS context. Refresh once and repeat the same request.
    res=await mutateRequest(path,method,body,true);
  }
  return parse<T>(res);
}

async function uploadRequest(path:string,form:FormData,forceSession=false){
  const csrf=await ensureSession(forceSession);
  return fetch(path,{
    method:'POST',
    credentials:'same-origin',
    headers:{'X-CSRF-Token':csrf},
    body:form,
  });
}

export async function apiUpload<T>(path:string,form:FormData):Promise<T>{
  let res=await uploadRequest(path,form);
  if(res.status===401||res.status===403){
    res=await uploadRequest(path,form,true);
  }
  return parse<T>(res);
}
