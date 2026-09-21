const asynchandler=(fn)=>async(req, res, next)=>{
    try{
        await fn(req, res, next)
    }
    catch(err){
        console.error("Error caught in asyncHandler:", err);
        res.status(err.statusCode || 500).json({
            success: false,
            message: err.message,
        })
    }
}

export {asynchandler}



// const asyncHandler = (requestHandler) => {
//     return (req,res,next) => {
//         Promise.resolve(requestHandler(req, res, next)).
//         catch((err)=>next(err))
//     }
// }